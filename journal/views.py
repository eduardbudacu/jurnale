import json
import os
import re
from collections import Counter
from pathlib import Path

import numpy as np
from django.contrib.auth import views as auth_views
from django.contrib.messages.views import SuccessMessageMixin
from django.db import connection
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from django.utils.safestring import mark_safe

from .models import Journal, Page, PageMetadata, PageMetadataTag
from .services.search import embed_query, excerpt, retrieve_pages

# RAG ("Ask your journals") — answer synthesis uses the OpenAI chat API.
ANSWER_MODEL = os.environ.get("ANSWER_MODEL", "gpt-4o")
RAG_TOP_K = int(os.environ.get("RAG_TOP_K", "8"))

RAG_SYSTEM_PROMPT = (
    "You are a warm, thoughtful assistant helping someone explore their own "
    "handwritten personal journals. Answer the question using ONLY the journal "
    "excerpts provided below — do not invent events, dates, or names that are not "
    "in the excerpts. The journals may be written in English, Dutch, or Romanian; "
    "answer in the same language as the question. When you draw on an excerpt, cite "
    "it with its bracketed number, e.g. [1] or [2][3]. If the excerpts do not "
    "contain enough to answer, say so honestly rather than guessing. Be concise."
)


class PasswordChangeView(SuccessMessageMixin, auth_views.PasswordChangeView):
    template_name = "journal/password_change.html"
    success_url = reverse_lazy("index")
    success_message = "Your password was changed."
    extra_context = {"title": "Change password"}


def _dictfetchall(cursor) -> list[dict]:
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def index(request):
    journals = list(
        Journal.objects.annotate(
            done=Count("pages", filter=Q(pages__status="done")),
            pending=Count("pages", filter=Q(pages__status="pending")),
            failed=Count("pages", filter=Q(pages__status="failed")),
        ).order_by("filename")
    )
    for j in journals:
        j.pct = round(j.done / j.page_count * 100) if j.page_count else 0

    total_pages = Page.objects.count()
    done_pages = Page.objects.filter(status="done").count()
    pct = round(done_pages / total_pages * 100) if total_pages else 0

    return render(request, "journal/journals.html", {
        "title": "Journals", "journals": journals, "total_journals": len(journals),
        "total_pages": total_pages, "done_pages": done_pages, "pct": pct,
    })


def journal_pages(request, journal_id):
    journal = get_object_or_404(Journal, id=journal_id)
    pages = list(journal.pages.order_by("page_number"))

    done = sum(1 for p in pages if p.status == "done")
    pending = sum(1 for p in pages if p.status == "pending")
    for p in pages:
        p.chars = len(p.ocr_text) if p.ocr_text else 0

    return render(request, "journal/pages.html", {
        "title": journal.filename, "journal": journal, "pages": pages,
        "done": done, "pending": pending,
    })


def page_detail(request, journal_id, page_number):
    journal = get_object_or_404(Journal, id=journal_id)
    page = get_object_or_404(Page, journal_id=journal_id, page_number=page_number)

    prev_num = page_number - 1 if page_number > 1 else None
    next_num = page_number + 1 if page_number < (journal.page_count or 0) else None

    metadata = PageMetadata.objects.filter(page_id=page.id, status="done").first()
    meta_tags = []
    if metadata:
        meta_tags = list(
            PageMetadataTag.objects.filter(page_metadata_id=metadata.id)
            .order_by("tag")
            .values_list("tag", flat=True)
        )

    return render(request, "journal/page_detail.html", {
        "title": f"Page {page_number}", "journal": journal, "page": page,
        "prev": prev_num, "next": next_num, "metadata": metadata, "meta_tags": meta_tags,
    })


def tags_view(request):
    tags = list(
        PageMetadataTag.objects.values("tag").annotate(cnt=Count("id")).order_by("-cnt")
    )
    total_pages = PageMetadataTag.objects.values("page_metadata_id").distinct().count()

    max_cnt = tags[0]["cnt"] if tags else 1
    for t in tags:
        t["pct"] = round(t["cnt"] / max_cnt * 100)

    return render(request, "journal/tags.html", {
        "title": "Tags", "tags": tags, "total_tags": len(tags), "total_pages": total_pages,
    })


def wordcloud_view(request):
    rows = Page.objects.filter(status="done", ocr_text__isnull=False).values_list(
        "ocr_text", flat=True
    )

    stop = _STOPWORDS
    counter = Counter()
    for text in rows:
        words = re.findall(r"[a-zA-ZÀ-ɏ]{3,}", text.lower())
        for w in words:
            if w not in stop and len(w) <= 30:
                counter[w] += 1

    top = counter.most_common(200)
    if not top:
        total_words = 0
        total_occ = 0
        words_json = "[]"
    else:
        total_words = len(top)
        total_occ = sum(c for _, c in top)
        max_count = top[0][1]
        min_count = top[-1][1]
        rng = max(max_count - min_count, 1)
        words_list = [[w, c, 12 + 36 * ((c - min_count) / rng)] for w, c in top]
        words_json = json.dumps(words_list)

    return render(request, "journal/wordcloud.html", {
        "title": "Word Cloud", "total_words": total_words,
        "total_occurrences": total_occ, "words_json": mark_safe(words_json),
    })


def embeddings_view(request):
    from sklearn.decomposition import PCA

    source = request.GET.get("source", "summary")
    if source not in ("summary", "content"):
        source = "summary"

    with connection.cursor() as cur:
        if source == "content":
            cur.execute("""
                SELECT pce.page_id, pce.embedding, pm.summary, pm.date_value,
                       p.journal_id, p.page_number,
                       string_agg(pmt.tag, ', ') as tags
                FROM page_content_embeddings pce
                JOIN pages p ON p.id = pce.page_id
                LEFT JOIN page_metadata pm ON pm.page_id = pce.page_id AND pm.status = 'done'
                LEFT JOIN page_metadata_tags pmt ON pmt.page_metadata_id = pm.id
                WHERE pce.status = 'done' AND pce.embedding IS NOT NULL
                GROUP BY pce.page_id, pce.embedding, pm.summary, pm.date_value,
                         p.journal_id, p.page_number
                ORDER BY pce.page_id
            """)
        else:
            cur.execute("""
                SELECT pse.page_id, pse.embedding, pm.summary, pm.date_value,
                       p.journal_id, p.page_number,
                       string_agg(pmt.tag, ', ') as tags
                FROM page_summary_embeddings pse
                JOIN page_metadata pm ON pm.page_id = pse.page_id
                JOIN pages p ON p.id = pse.page_id
                LEFT JOIN page_metadata_tags pmt ON pmt.page_metadata_id = pm.id
                WHERE pse.status = 'done' AND pse.embedding IS NOT NULL
                GROUP BY pse.page_id, pse.embedding, pm.summary, pm.date_value,
                         p.journal_id, p.page_number
                ORDER BY pse.page_id
            """)
        rows = _dictfetchall(cur)

    points_json = "[]"
    total_points = len(rows)

    if total_points >= 2:
        def _parse_embedding(val):
            if isinstance(val, (list, np.ndarray)):
                return val
            return json.loads(val)

        embeddings = np.array([_parse_embedding(r["embedding"]) for r in rows])
        n_components = min(2, embeddings.shape[0], embeddings.shape[1])
        coords = PCA(n_components=n_components).fit_transform(embeddings)

        points = []
        for i, r in enumerate(rows):
            points.append({
                "x": round(float(coords[i][0]), 4),
                "y": round(float(coords[i][1]), 4) if n_components == 2 else 0,
                "page_id": r["page_id"],
                "journal_id": r["journal_id"],
                "page_number": r["page_number"],
                "summary": (r["summary"] or ""),
                "date": r["date_value"],
                "tags": (r["tags"] or ""),
            })
        points_json = json.dumps(points)

    return render(request, "journal/embeddings.html", {
        "title": "Embeddings", "total_points": total_points,
        "points_json": mark_safe(points_json), "source": source,
    })


def search_view(request):
    query = request.GET.get("q", "").strip()
    try:
        limit = int(request.GET.get("n", "10"))
    except ValueError:
        limit = 10
    if limit not in (5, 10, 20, 50):
        limit = 10

    results = []
    error = None

    if query:
        try:
            query_vec = embed_query(query)
        except Exception as e:
            error = f"Failed to embed query: {e}"
            return render(request, "journal/search.html", {
                "title": "Search", "query": query, "limit": limit,
                "results": [], "error": error,
            })

        for r in retrieve_pages(query_vec, limit):
            results.append({
                "score": round(float(r["score"]), 4),
                "page_id": r["page_id"],
                "journal_id": r["journal_id"],
                "page_number": r["page_number"],
                "filename": r["filename"],
                "summary": r["summary"] or "",
                "date": r["date_value"] or "",
                "tags": [t for t in (r["tags"] or "").split(", ") if t],
            })

    return render(request, "journal/search.html", {
        "title": "Search", "query": query, "limit": limit,
        "results": results, "error": error,
    })


def _synthesize_answer(query: str, rows: list[dict]) -> str:
    """Build a grounded answer from retrieved pages using the OpenAI chat API."""
    from openai import OpenAI

    blocks = []
    for i, r in enumerate(rows, start=1):
        header = f"[{i}] {r['filename']} — page {r['page_number']}"
        if r["date_value"]:
            header += f" — {r['date_value']}"
        lines = [header]
        if r["summary"]:
            lines.append(f"Summary: {r['summary']}")
        lines.append(f"Excerpt:\n{excerpt(r['ocr_text'])}")
        blocks.append("\n".join(lines))
    context = "\n\n---\n\n".join(blocks)

    client = OpenAI()
    resp = client.chat.completions.create(
        model=ANSWER_MODEL,
        messages=[
            {"role": "system", "content": RAG_SYSTEM_PROMPT},
            {"role": "user", "content": f"Question: {query}\n\nJournal excerpts:\n\n{context}"},
        ],
        temperature=0.3,
        max_tokens=800,
    )
    return (resp.choices[0].message.content or "").strip()


def ask_view(request):
    query = request.GET.get("q", "").strip()
    answer = None
    sources = []
    error = None

    if query:
        try:
            query_vec = embed_query(query)
        except Exception as e:
            error = f"Failed to embed question: {e}"
            return render(request, "journal/ask.html", {
                "title": "Ask", "query": query, "answer": None, "sources": [], "error": error,
            })

        rows = retrieve_pages(query_vec, RAG_TOP_K)

        for i, r in enumerate(rows, start=1):
            sources.append({
                "n": i,
                "page_id": r["page_id"],
                "journal_id": r["journal_id"],
                "page_number": r["page_number"],
                "filename": r["filename"],
                "summary": r["summary"] or "",
                "date": r["date_value"] or "",
                "tags": [t for t in (r["tags"] or "").split(", ") if t],
                "score": round(float(r["score"]), 4),
            })

        if not rows:
            error = ("No journal pages have embeddings yet. Run the embeddings "
                     "workers first (embeddings_worker / content_embeddings_worker).")
        else:
            try:
                answer = _synthesize_answer(query, rows)
            except Exception as e:
                error = f"Failed to generate answer: {e}"

    return render(request, "journal/ask.html", {
        "title": "Ask", "query": query, "answer": answer, "sources": sources, "error": error,
    })


def serve_image(request, journal_id, page_number):
    page = (
        Page.objects.filter(journal_id=journal_id, page_number=page_number)
        .values_list("image_path", flat=True)
        .first()
    )
    if not page:
        raise Http404
    path = Path(page)
    if not path.exists():
        raise Http404
    return FileResponse(open(path, "rb"), content_type="image/png")


# Multilingual (en/nl/ro) stopword set used by the word cloud.
_STOPWORDS = {
    'the','a','an','and','or','but','in','on','at','to','for','of','is','it','that','was','with',
    'as','are','be','this','have','from','had','not','by','were','been','has','its','can','all',
    'will','my','i','me','we','he','she','they','you','her','his','their','our','your','him',
    'do','did','so','if','no','up','out','just','about','would','one','them','then','than',
    'when','what','there','which','more','some','could','into','other','also','very','each',
    'how','may','much','these','like','after','many','most','made','over','such','even','back',
    'only','come','where','get','got','am','been','being','does','done','going','went','said',
    'know','think','see','make','want','time','day','good','new','now','way','because','any',
    'still','well','here','should','own','too','through','right','before','take','long','same',
    'another','while','around','again','off','down','really','thing','us','those','every',
    'between','few','both','under','never','always','however','though','since','during','without',
    'something','anything','everything','nothing','someone','anyone','everyone','already','away',
    'things','first','last','next','might','need','keep','let','put','say','tell','give','use',
    'work','call','try','ask','seem','feel','leave','turn','look','show','hear','play','run',
    'move','live','believe','bring','happen','write','provide','sit','stand','lose','pay','meet',
    'include','continue','set','learn','change','lead','understand','watch','follow','stop','create',
    'speak','read','allow','add','spend','grow','open','walk','win','offer','remember','love',
    'consider','appear','buy','wait','serve','die','send','expect','build','stay','fall','cut',
    'reach','kill','remain','suggest','raise','pass','sell','require','report','decide','pull',
    'able','often','enough','quite','rather','ago','yet','upon','almost','along','today',
    'went','came','thought','found','took','left','told','asked','looked','seemed','called',
    'used','tried','started','became','wanted','needed','gave','felt','saw','knew','got',
    'being','having','getting','making','going','coming','saying','taking',
    'de','het','en','van','een','dat','die','er','te','op','aan','om','maar','ook','met',
    'nog','bij','uit','dan','wel','na','over','al','heb','ben','ze','wat','kan','moet',
    'mijn','niet','naar','voor','was','had','zijn','haar','hem','dit','werd','zou','geen',
    'ik','je','hij','we','wij','zij','hun','ons','meer','zeer','veel','tot','als','toch',
    'worden','worden','heeft','hebben','deze','door','waar','kan','zal','laten','maken',
    'gaan','komen','moeten','willen','zullen','mogen','doen','staan','geven','nemen','zien',
    'vinden','weten','denken','voelen','houden','blijven','lopen','zitten','liggen',
    'si','sa','nu','dar','sau','care','este','sunt','fost','mai','din','pentru','fie',
    'cum','foarte','apoi','deci','ori','nici','doar','deja','inca','chiar','iar','totusi',
    'despre','prin','spre','sub','peste','fara','contra','dintre','pana','dupa',
    'cel','cea','cei','cele','ale','lui','lor','sau','ori',
    'sunt','este','era','eram','erat','fie','fiind','fost',
    'pot','poti','poate','putem','puteti','pot',
    'trebuie','vreau','vrei','vrea','vrem','vreti','vor',
    'fac','faci','face','facem','faceti','fac',
    'stiu','stii','stie','stim','stiti','stiu',
    'zic','zici','zice','zicem','ziceti','zic',
    'dau','dai','dea','dam','dati','dau',
    'iau','iei','iea','iam','iati','iau',
    'las','lasi','lasa','lasam','lasati','lasa',
    'pun','pui','pune','punem','puneti','pun',
    'vin','vii','vine','venim','veniti','vin',
    'meu','mea','mei','mele','tau','tea','tai','tale',
    'sau','nostru','noastra','nostri','noastre','vostru','voastra','vostri','voastre',
    'acest','aceasta','acesta','aceste','acestia','acestea','acel','acea','acei','acele',
    'ela','eala','elei','elelor','lui','lor',
    'unde','cand','cat','cata','cati','cate','cum','daca',
    'atunci','acum','aici','acolo','asa','astfel','altfel',
    'cineva','ceva','nimeni','nimic','fiecare','orice','oricare','oricine',
    'alt','alta','alti','alte','altul','alta','altii','altele',
    'tot','toata','toti','toate','totul',
    'unul','una','unii','unele',
    'noi','voi','ele','lor','noi','voi',
    'avea','avem','aveti','aveau','aveam','aveai','avea',
    'mie','tie','noua','voua','sie',
    'cine','ceea','cele','cei',
    'insa','desi','fiindca','deoarece','intrucat','precum','inainte',
    'acum','mereu','intotdeauna','niciodata','uneori','cateodata','adesea',
    'sus','jos','inauntru','afara','inapoi','inainte',
    'bine','rau','mult','putin','destul','prea','cam','tocmai','macar',
    'numa','numai','cat','cand','unde','cum','daca',
    'și','să','că','în','în','pe','la','cu','nu','ca','mai','dar','sau',
    'care','care','este','sunt','fost','era','sunt','este','era',
    'când','cât','câtă','câți','câte','după','până','fără','între',
    'într','într','încă','într','într',
    'făcut','știu','știi','știe','știm','știți','știu',
    'această','acestă','acești','aceste','câțiva',
    'lucru','lucruri','fel','parte','mod','loc',
    'illegible','page','text','image','unable','provide','appears','contain',
}
