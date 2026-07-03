(function () {
  const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const revealTargets = document.querySelectorAll(".stagger > *, .card");
  if ("IntersectionObserver" in window && !prefersReduced) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
    revealTargets.forEach((item, index) => {
      item.style.animationDelay = `${Math.min(index * 70, 420)}ms`;
      observer.observe(item);
    });
  } else {
    revealTargets.forEach((item) => item.classList.add("is-visible"));
  }

  function ping() {
    fetch("/api/ping", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ page: window.location.pathname, timestamp: new Date().toISOString() })
    }).catch(() => {});
  }
  ping();
  window.setInterval(ping, 60000);

  document.querySelectorAll(".mobile-tabbar a, .desktop-nav a").forEach((link) => {
    const linkPath = new URL(link.href, window.location.origin).pathname;
    if (linkPath === window.location.pathname) {
      link.setAttribute("aria-current", "page");
    }
  });

  document.querySelectorAll("[data-count]").forEach((node) => {
    const target = Number(node.dataset.count || 0);
    if (prefersReduced) {
      node.textContent = target;
      return;
    }
    const start = performance.now();
    function tick(time) {
      const progress = Math.min((time - start) / 700, 1);
      node.textContent = Math.round(target * progress);
      if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  });

  document.querySelectorAll("[data-progress-number]").forEach((node) => {
    const target = Number(node.dataset.progressNumber || 0);
    if (prefersReduced) {
      node.textContent = target;
      return;
    }
    const start = performance.now();
    function tick(time) {
      const progress = Math.min((time - start) / 900, 1);
      node.textContent = Math.round(target * progress);
      if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  });

  document.querySelectorAll("[data-listen-url]").forEach((button) => {
    button.addEventListener("click", async () => {
      const original = button.textContent;
      button.disabled = true;
      button.textContent = "Marcando...";
      try {
        const response = await fetch(button.dataset.listenUrl, { method: "POST" });
        const data = await response.json();
        button.textContent = data.ok ? "Áudio ouvido" : original;
        button.classList.toggle("unlock-pulse", data.ok);
      } catch (error) {
        button.textContent = original;
      } finally {
        setTimeout(() => { button.disabled = false; }, 700);
      }
    });
  });

  document.querySelectorAll(".lesson-complete-form").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("button[type='submit']");
      const feedback = document.querySelector(".lesson-feedback");
      const answer = form.querySelector("textarea[name='answer']").value;
      button.disabled = true;
      button.textContent = "Concluindo...";
      try {
        const response = await fetch(form.dataset.completeUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ answer })
        });
        const data = await response.json();
        if (feedback) {
          feedback.hidden = false;
          feedback.textContent = data.message;
          feedback.classList.add("is-visible");
        }
        if (data.ok) {
          button.textContent = "Etapa concluída";
          setTimeout(() => { window.location.href = "/estacoes"; }, 1200);
        } else {
          button.textContent = "Concluir exercício e liberar próxima aula";
          button.disabled = false;
        }
      } catch (error) {
        if (feedback) {
          feedback.hidden = false;
          feedback.textContent = "Não foi possível concluir agora. Tente novamente.";
          feedback.classList.add("is-visible");
        }
        button.textContent = "Concluir exercício e liberar próxima aula";
        button.disabled = false;
      }
    });
  });

  const canvas = document.getElementById("radarChart");
  if (!canvas) return;
  const scores = JSON.parse(canvas.dataset.scores || "{}");
  const labels = Object.keys(scores);
  const ctx = canvas.getContext("2d");
  const cx = canvas.width / 2;
  const cy = canvas.height / 2 + 8;
  const radius = Math.min(canvas.width, canvas.height) * 0.34;

  function point(index, value) {
    const angle = -Math.PI / 2 + (Math.PI * 2 * index) / labels.length;
    const r = radius * value;
    return [cx + Math.cos(angle) * r, cy + Math.sin(angle) * r];
  }

  function draw(progress) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.lineWidth = 1;
    ctx.font = "15px Arial";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    for (let level = 1; level <= 5; level += 1) {
      ctx.beginPath();
      labels.forEach((_, index) => {
        const [x, y] = point(index, level / 5);
        if (index === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.closePath();
      ctx.strokeStyle = "rgba(255, 244, 223, .16)";
      ctx.stroke();
    }

    labels.forEach((label, index) => {
      const [x, y] = point(index, 1.15);
      ctx.fillStyle = "#FFF4DF";
      ctx.fillText(label, x, y);
      const [ax, ay] = point(index, 1);
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(ax, ay);
      ctx.strokeStyle = "rgba(229, 192, 107, .16)";
      ctx.stroke();
    });

    ctx.beginPath();
    labels.forEach((label, index) => {
      const value = (scores[label].percent / 100) * progress;
      const [x, y] = point(index, value);
      if (index === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.closePath();
    ctx.fillStyle = "rgba(184, 137, 47, .26)";
    ctx.strokeStyle = "#E5C06B";
    ctx.lineWidth = 2;
    ctx.fill();
    ctx.stroke();
  }

  if (prefersReduced) {
    draw(1);
  } else {
    const started = performance.now();
    function animate(time) {
      const progress = Math.min((time - started) / 700, 1);
      draw(progress);
      if (progress < 1) requestAnimationFrame(animate);
    }
    requestAnimationFrame(animate);
  }
})();
