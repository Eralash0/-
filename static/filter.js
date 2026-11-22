document.querySelectorAll(".filter-bar").forEach(function (bar) {
    var box = document.getElementById(bar.dataset.target);
    if (!box) return;

    var items = Array.prototype.slice.call(box.querySelectorAll("[data-row]"));
    var search = bar.querySelector(".f-search");
    var from = bar.querySelector(".f-from");
    var to = bar.querySelector(".f-to");
    var min = bar.querySelector(".f-min");
    var max = bar.querySelector(".f-max");
    var reset = bar.querySelector(".f-reset");
    var count = bar.querySelector(".f-count");

    function apply() {
        var q = search ? search.value.trim().toLowerCase() : "";
        var shown = 0;

        items.forEach(function (el) {
            var ok = true;

            if (q && el.textContent.toLowerCase().indexOf(q) === -1) ok = false;

            var date = el.dataset.date;
            if (date) {
                if (from && from.value && date < from.value) ok = false;
                if (to && to.value && date > to.value) ok = false;
            }

            var p = parseFloat(el.dataset.percent);
            if (!isNaN(p)) {
                if (min && min.value !== "" && p < parseFloat(min.value)) ok = false;
                if (max && max.value !== "" && p > parseFloat(max.value)) ok = false;
            }

            el.style.display = ok ? "" : "none";
            if (ok) shown++;
        });

        var isRu = document.documentElement.lang === "ru";
if (count) count.textContent = (isRu ? "Найдено: " : "Табылды: ") + shown + " / " + items.length;
    }

    bar.addEventListener("input", apply);

    if (reset) {
        reset.addEventListener("click", function () {
            bar.querySelectorAll("input").forEach(function (i) { i.value = ""; });
            apply();
        });
    }

    apply();
});