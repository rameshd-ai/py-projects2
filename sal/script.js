(function () {
  'use strict';

  // Close mobile menu when a nav link is clicked (Bootstrap collapse)
  var navLinks = document.querySelectorAll('#navbarMain .nav-link, #navbarMain .btn-book');
  var navbarCollapse = document.getElementById('navbarMain');
  var bsCollapse = navbarCollapse && bootstrap.Collapse.getInstance(navbarCollapse);

  navLinks.forEach(function (link) {
    link.addEventListener('click', function () {
      if (window.innerWidth < 992 && navbarCollapse && navbarCollapse.classList.contains('show')) {
        var toggle = document.querySelector('.navbar-toggler');
        if (toggle) toggle.click();
      }
    });
  });

  // Optional: subtle header background on scroll
  var header = document.querySelector('.main-header');
  if (header) {
    window.addEventListener('scroll', function () {
      if (window.scrollY > 50) {
        header.style.boxShadow = '0 2px 12px rgba(0,0,0,0.08)';
      } else {
        header.style.boxShadow = '0 1px 0 rgba(0,0,0,0.06)';
      }
    });
  }
})();
