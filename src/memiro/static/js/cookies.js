// Cookie-баннер: запоминает выбор посетителя в cookie. Решение о том,
// попадёт ли Метрика в разметку, принимает сервер (memiro/legal/consent.py),
// поэтому «Принять» перезагружает страницу — счётчик приезжает уже
// с сервера, а не собирается здесь из номера, который до согласия
// в HTML не отдаётся вовсе. «Отклонить» перезагрузки не требует.
(() => {
  const banner = document.querySelector("[data-cookie-banner]");
  if (!banner) return;

  // Secure только под https: на http-разработке такую cookie
  // браузер бы отбросил, и баннер не запоминал бы выбор
  const secure = window.location.protocol === "https:" ? "; secure" : "";

  const remember = (value) => {
    const { cookie, maxAge } = banner.dataset;
    document.cookie =
      `${cookie}=${value}; path=/; max-age=${maxAge}; samesite=lax${secure}`;
  };

  banner.querySelector("[data-cookie-accept]").addEventListener("click", () => {
    remember(banner.dataset.accepted);
    window.location.reload();
  });

  banner.querySelector("[data-cookie-decline]").addEventListener("click", () => {
    remember(banner.dataset.declined);
    banner.remove();
  });
})();
