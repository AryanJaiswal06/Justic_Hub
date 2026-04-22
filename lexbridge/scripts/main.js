/* ============================================================
   LexBridge — scripts/main.js
   Shared utilities loaded on every page:
   - showToast()
   - toggleSidebar() / toggleNotif()
   - showTab()
   - Navbar scroll effect + hamburger menu
   - Homepage: testimonials, lawyer grid helpers
   ============================================================ */

/* ── Toast ────────────────────────────────────────────────── */
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    toast.style.transition = '0.3s ease';
    setTimeout(() => toast.remove(), 320);
  }, 3200);
}

/* ── Sidebar toggle (dashboards) ─────────────────────────── */
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  if (!sidebar) return;
  // On mobile, toggle 'open'; on desktop toggle 'collapsed'
  if (window.innerWidth <= 768) {
    sidebar.classList.toggle('open');
  } else {
    sidebar.classList.toggle('collapsed');
    const main = document.querySelector('.dash-main');
    if (main) main.style.marginLeft = sidebar.classList.contains('collapsed') ? '0' : '260px';
  }
}

/* ── Notification dropdown ────────────────────────────────── */
function toggleNotif() {
  const dropdown = document.getElementById('notifDropdown');
  if (!dropdown) return;
  const isOpen = dropdown.style.display !== 'none';
  dropdown.style.display = isOpen ? 'none' : 'block';

  if (!isOpen) {
    // Close on outside click
    setTimeout(() => {
      document.addEventListener('click', function close(e) {
        if (!dropdown.contains(e.target) && e.target.id !== 'notifBtn') {
          dropdown.style.display = 'none';
          document.removeEventListener('click', close);
        }
      });
    }, 10);
  }
}

/* ── Tab switcher (dashboards) ────────────────────────────── */
function showTab(name) {
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  const tab = document.getElementById('tab-' + name);
  if (tab) tab.classList.add('active');

  const titleEl = document.getElementById('pageTitle');
  if (titleEl) {
    const titles = {
      overview: 'Dashboard Overview', cases: 'My Cases', documents: 'Documents',
      messages: 'Messages', newcase: 'New Case Request', billing: 'Billing',
      settings: 'Account Settings', profile: 'My Profile', earnings: 'Earnings',
      ratings: 'Ratings & Reviews', requests: 'Case Requests', active: 'Active Cases',
      users: 'User Management', lawyers: 'Lawyer Management', analytics: 'Analytics',
      disputes: 'Disputes', verifications: 'Verifications', reports: 'Reports',
    };
    titleEl.textContent = titles[name] || name;
  }
}

/* ── Password toggle helper (auth pages) ──────────────────── */
function togglePassword(inputId, btn) {
  const input = document.getElementById(inputId);
  if (!input) return;
  if (input.type === 'password') {
    input.type = 'text';
    btn.textContent = '🙈';
    // Auto-hide after 3 s for security
    setTimeout(() => {
      input.type = 'password';
      btn.textContent = '👁';
    }, 3000);
  } else {
    input.type = 'password';
    btn.textContent = '👁';
  }
}

/* ── Navbar: scroll shadow + hamburger menu ───────────────── */
(function initNavbar() {
  const navbar = document.getElementById('navbar');
  if (!navbar) return;

  // Scroll effect
  window.addEventListener('scroll', () => {
    navbar.classList.toggle('scrolled', window.scrollY > 20);
  }, { passive: true });

  // Hamburger toggle
  const hamburger = document.getElementById('hamburger');
  const navLinks  = document.getElementById('navLinks');
  if (hamburger && navLinks) {
    hamburger.addEventListener('click', () => {
      navLinks.classList.toggle('open');
      const spans = hamburger.querySelectorAll('span');
      const isOpen = navLinks.classList.contains('open');
      if (spans.length >= 3) {
        spans[0].style.transform = isOpen ? 'rotate(45deg) translate(5px,5px)' : '';
        spans[1].style.opacity   = isOpen ? '0' : '1';
        spans[2].style.transform = isOpen ? 'rotate(-45deg) translate(5px,-5px)' : '';
      }
    });
    // Close on link click
    navLinks.querySelectorAll('a').forEach(a => {
      a.addEventListener('click', () => navLinks.classList.remove('open'));
    });
  }
})();

/* ── Testimonials data & renderer (homepage) ──────────────── */
const TESTIMONIALS = [
  { name: 'Ananya Mehta', role: 'Property Dispute Client', stars: 5, text: 'LexBridge connected me with an excellent property lawyer within hours. The case tracker kept me informed at every step — I never had to chase for updates.' },
  { name: 'Rajiv Nair', role: 'Corporate Client', stars: 5, text: 'Outstanding platform. The document vault and secure messaging made collaborating with my lawyer seamless. Resolved a complex contract dispute in record time.' },
  { name: 'Sunita Patel', role: 'Family Law Client', stars: 5, text: 'Dealing with a difficult family matter, I needed a compassionate and experienced lawyer. LexBridge matched me perfectly. Highly recommended.' },
];

function renderTestimonials() {
  const grid = document.getElementById('testimonialsGrid');
  if (!grid) return;
  grid.innerHTML = TESTIMONIALS.map(t => `
    <div class="testimonial-card">
      <div class="t-stars">${'★'.repeat(t.stars)}</div>
      <p class="t-text">"${t.text}"</p>
      <div class="t-author">
        <div class="t-avatar">${t.name.split(' ').map(w => w[0]).join('').slice(0, 2)}</div>
        <div>
          <div class="t-name">${t.name}</div>
          <div class="t-role">${t.role}</div>
        </div>
      </div>
    </div>`).join('');
}

/* ── Animate counter (homepage hero stats) ────────────────── */
function animateCount(el, target, suffix = '') {
  if (!el) return;
  const duration = 1400;
  const steps    = 60;
  const stepVal  = Math.ceil(target / steps);
  let   current  = 0;
  const timer = setInterval(() => {
    current = Math.min(current + stepVal, target);
    el.textContent = current.toLocaleString('en-IN') + suffix;
    if (current >= target) clearInterval(timer);
  }, duration / steps);
}

/* ── Run on DOM ready ─────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  renderTestimonials();

  // Intersection observer for fade-in animations
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) { e.target.style.animationPlayState = 'running'; observer.unobserve(e.target); }
      });
    }, { threshold: 0.1 });
    document.querySelectorAll('.animate-fadeInUp').forEach(el => {
      el.style.animationPlayState = 'paused';
      observer.observe(el);
    });
  }

  // Active nav link highlight on scroll (homepage)
  const sections = document.querySelectorAll('section[id]');
  if (sections.length) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          document.querySelectorAll('.nav-links a').forEach(a => a.classList.remove('active'));
          const link = document.querySelector(`.nav-links a[href="#${e.target.id}"]`);
          if (link) link.classList.add('active');
        }
      });
    }, { rootMargin: '-40% 0px -55% 0px' });
    sections.forEach(s => io.observe(s));
  }
});
