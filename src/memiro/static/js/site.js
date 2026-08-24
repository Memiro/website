// Мелочи разметки, общие нескольким скриптам страницы. Скрипты живут
// каждый в своей области видимости, а site.js грузится первым — общему
// месту больше быть негде, и второй копии форматирования цены хватило,
// чтобы она однажды разошлась с фильтром `rub` в шаблонах.
window.memiro = {
  // Разбивка тысяч узким неразрывным пробелом — как `catalog.formatting.rub`
  rub: (value) => String(value).replace(/\B(?=(\d{3})+(?!\d))/g, "\u202F"),
};

// Мобильное меню: раскрытие «Меню»-пилюли
(() => {
  const toggle = document.querySelector("[data-menu-toggle]");
  const menu = document.getElementById("mobile-menu");
  if (!toggle || !menu) return;
  toggle.addEventListener("click", () => {
    const open = menu.hidden;
    menu.hidden = !open;
    toggle.setAttribute("aria-expanded", String(open));
  });
})();
