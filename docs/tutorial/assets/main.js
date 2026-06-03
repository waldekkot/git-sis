/* ================================================================
   git-sis tutorial – shared JS
   Copy buttons, scroll-reveal, keyboard prev/next nav
   ================================================================ */

// Page manifest (title, filename) – drives prev/next and progress pill
const PAGES = [
  { title: "Overview",     file: "index.html" },
  { title: "Setup",        file: "01-setup.html" },
  { title: "Local Dev",    file: "02-local-dev.html" },
  { title: "GitHub",       file: "03-github.html" },
  { title: "Deploy to SiS",file: "04-deploy.html" },
  { title: "CI/CD",        file: "05-cicd.html" },
];

function currentPageIndex() {
  const name = location.pathname.split("/").pop() || "index.html";
  return PAGES.findIndex(p => p.file === name);
}

// ── Progress bar fill ──────────────────────────────────────────────
function initProgress() {
  const fill = document.querySelector(".progress-fill");
  if (!fill) return;
  const idx = currentPageIndex();
  const total = PAGES.length - 1;
  fill.style.width = `${((idx < 0 ? 0 : idx) / total) * 100}%`;
}

// ── Page pill ─────────────────────────────────────────────────────
function initPill() {
  const pill = document.querySelector(".nav-pill");
  if (!pill) return;
  const idx = currentPageIndex();
  pill.textContent = `${idx < 0 ? 1 : idx + 1} / ${PAGES.length}`;
}

// ── Prev / Next buttons ───────────────────────────────────────────
function initNav() {
  const idx = currentPageIndex();
  const prevBtn = document.getElementById("btn-prev");
  const nextBtn = document.getElementById("btn-next");

  if (prevBtn) {
    if (idx > 0) {
      const prev = PAGES[idx - 1];
      prevBtn.href = prev.file;
      prevBtn.querySelector(".nav-btn-label").textContent = "Previous";
      prevBtn.querySelector(".nav-btn-title").textContent = prev.title;
    } else {
      prevBtn.style.visibility = "hidden";
    }
  }

  if (nextBtn) {
    if (idx < PAGES.length - 1 && idx >= 0) {
      const next = PAGES[idx + 1];
      nextBtn.href = next.file;
      nextBtn.querySelector(".nav-btn-label").textContent = "Next";
      nextBtn.querySelector(".nav-btn-title").textContent = next.title;
    } else {
      nextBtn.style.visibility = "hidden";
    }
  }
}

// ── Keyboard navigation ───────────────────────────────────────────
function initKeyboard() {
  document.addEventListener("keydown", e => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
    const idx = currentPageIndex();
    if ((e.key === "ArrowRight" || e.key === "l") && idx < PAGES.length - 1 && idx >= 0) {
      location.href = PAGES[idx + 1].file;
    }
    if ((e.key === "ArrowLeft" || e.key === "h") && idx > 0) {
      location.href = PAGES[idx - 1].file;
    }
  });
}

// ── Copy buttons ──────────────────────────────────────────────────
function initCopyButtons() {
  document.querySelectorAll(".code-block").forEach(block => {
    const btn = block.querySelector(".copy-btn");
    const pre = block.querySelector("pre");
    if (!btn || !pre) return;

    btn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(pre.textContent.trim());
        btn.textContent = "Copied!";
        btn.classList.add("copied");
        setTimeout(() => {
          btn.textContent = "Copy";
          btn.classList.remove("copied");
        }, 2000);
      } catch {
        btn.textContent = "Error";
      }
    });
  });
}

// ── Scroll-reveal (IntersectionObserver) ─────────────────────────
function initReveal() {
  const observer = new IntersectionObserver(
    entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12, rootMargin: "0px 0px -30px 0px" }
  );

  document.querySelectorAll(".reveal").forEach(el => observer.observe(el));
}

// ── SVG animation triggers ────────────────────────────────────────
// Diagrams with class "svg-anim" restart their CSS animations when
// they scroll into view (by toggling a class).
function initSvgAnims() {
  const obs = new IntersectionObserver(
    entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add("playing");
        }
      });
    },
    { threshold: 0.3 }
  );
  document.querySelectorAll(".svg-anim").forEach(el => obs.observe(el));
}

// ── Boot ─────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  initProgress();
  initPill();
  initNav();
  initKeyboard();
  initCopyButtons();
  initReveal();
  initSvgAnims();
});
