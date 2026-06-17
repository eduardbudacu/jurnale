function initWordCloud(words) {
  const canvas = document.getElementById('cloud-canvas');
  const container = document.getElementById('cloud-container');
  const ctx = canvas.getContext('2d');

  let W, H, cx, cy;
  function resize() {
    W = container.clientWidth; H = container.clientHeight;
    canvas.width = W; canvas.height = H;
    cx = W / 2; cy = H / 2;
  }
  resize();
  window.addEventListener('resize', resize);

  const N = words.length;
  const radius = Math.min(W, H) * 0.38;
  const points = [];

  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < N; i++) {
    const y = 1 - (i / (N - 1)) * 2;
    const r = Math.sqrt(1 - y * y);
    const theta = goldenAngle * i;
    points.push({
      x: Math.cos(theta) * r * radius,
      y: y * radius,
      z: Math.sin(theta) * r * radius,
      word: words[i][0],
      count: words[i][1],
      size: words[i][2]
    });
  }

  let rotX = 0, rotY = 0;
  let dragging = false, lastMX = 0, lastMY = 0;
  let velX = 0, velY = 0.003;

  container.addEventListener('mousedown', e => { dragging = true; lastMX = e.clientX; lastMY = e.clientY; velX = 0; velY = 0; container.style.cursor = 'grabbing'; });
  window.addEventListener('mouseup', () => { dragging = false; container.style.cursor = 'grab'; });
  window.addEventListener('mousemove', e => {
    if (!dragging) return;
    const dx = e.clientX - lastMX, dy = e.clientY - lastMY;
    velY = dx * 0.0004; velX = dy * 0.0004;
    rotY += dx * 0.005; rotX += dy * 0.005;
    lastMX = e.clientX; lastMY = e.clientY;
  });

  container.addEventListener('touchstart', e => { dragging = true; lastMX = e.touches[0].clientX; lastMY = e.touches[0].clientY; velX = 0; velY = 0; }, {passive: true});
  window.addEventListener('touchend', () => { dragging = false; });
  window.addEventListener('touchmove', e => {
    if (!dragging) return;
    const dx = e.touches[0].clientX - lastMX, dy = e.touches[0].clientY - lastMY;
    velY = dx * 0.0004; velX = dy * 0.0004;
    rotY += dx * 0.005; rotX += dy * 0.005;
    lastMX = e.touches[0].clientX; lastMY = e.touches[0].clientY;
  }, {passive: true});

  const colors = ['#58a6ff','#3fb950','#d29922','#f85149','#bc8cff','#f778ba','#79c0ff','#7ee787','#e3b341','#ffa198'];

  function rotatePoint(px, py, pz) {
    let y1 = py * Math.cos(rotX) - pz * Math.sin(rotX);
    let z1 = py * Math.sin(rotX) + pz * Math.cos(rotX);
    let x2 = px * Math.cos(rotY) + z1 * Math.sin(rotY);
    let z2 = -px * Math.sin(rotY) + z1 * Math.cos(rotY);
    return { x: x2, y: y1, z: z2 };
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);
    if (!dragging) {
      rotY += velY; rotX += velX;
      velX *= 0.998; velY *= 0.998;
      if (Math.abs(velY) < 0.001 && !dragging) velY = 0.003;
    }
    const projected = points.map((p, i) => {
      const r = rotatePoint(p.x, p.y, p.z);
      const perspective = 800 / (800 + r.z);
      return { ...p, sx: cx + r.x * perspective, sy: cy + r.y * perspective, sz: r.z, perspective, idx: i };
    });
    projected.sort((a, b) => a.sz - b.sz);
    for (const p of projected) {
      const alpha = 0.3 + 0.7 * ((p.sz + radius) / (2 * radius));
      const fontSize = Math.max(10, p.size * p.perspective);
      ctx.font = `${Math.round(fontSize)}px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`;
      ctx.fillStyle = colors[p.idx % colors.length];
      ctx.globalAlpha = alpha;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(p.word, p.sx, p.sy);
    }
    ctx.globalAlpha = 1;
    requestAnimationFrame(draw);
  }
  draw();
}
