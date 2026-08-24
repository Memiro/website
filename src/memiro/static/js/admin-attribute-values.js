// Значения справочника в строке характеристики — только выбранного
// атрибута. Разметку даёт AttributeValueSelect: у каждого <option>
// стоит data-attribute. Без скрипта список полон и разложен по
// группам — владелец найдёт значение, просто дольше.
(function () {
  "use strict";

  var VALUES = 'select[name$="-value_option"]';
  var ATTRIBUTE = 'select[name$="-attribute"]';

  function sync(row) {
    if (!row) {
      return;
    }
    var attribute = row.querySelector(ATTRIBUTE);
    var values = row.querySelector(VALUES);
    if (!attribute || !values) {
      return;
    }
    var chosen = attribute.value;
    values.querySelectorAll("option[data-attribute]").forEach(function (option) {
      // Пустой выбор атрибута оставляет список полным: сужать не по
      // чему, а спрятать всё значило бы показать пустоту
      var fits = !chosen || option.dataset.attribute === chosen;
      option.hidden = !fits;
      option.disabled = !fits;
      if (!fits && option.selected) {
        values.value = "";
      }
    });
    values.querySelectorAll("optgroup").forEach(function (group) {
      group.hidden = !group.querySelector("option:not([hidden])");
    });
  }

  function rows() {
    // Строка-шаблон `-empty` пропускается: админка клонирует её на
    // «Добавить ещё», и спрятанное в ней уехало бы в каждую новую
    return Array.prototype.filter.call(
      document.querySelectorAll("tr[id], .inline-related[id]"),
      function (row) {
        return (
          row.id.indexOf("-empty") === -1 && row.querySelector(VALUES) !== null
        );
      }
    );
  }

  // Событие слушается на документе, а не на каждом select: строки
  // рождаются и после загрузки, а делегированный слушатель достаётся
  // им даром — и не клонируется вместе с разметкой
  document.addEventListener("change", function (event) {
    if (event.target.matches && event.target.matches(ATTRIBUTE)) {
      sync(event.target.closest("tr, .inline-related"));
    }
  });

  document.addEventListener("formset:added", function (event) {
    sync(event.target);
  });

  document.addEventListener("DOMContentLoaded", function () {
    rows().forEach(sync);
  });
})();
