(function () {
    "use strict";

    console.log("VetClinic Admin JS — Premium Dark Teal Theme");

    /* =====================================================
       TIL ANIQLASH
       ===================================================== */

    function getLang() {
        const htmlLang = document.documentElement.lang;
        if (htmlLang) return htmlLang.toLowerCase().slice(0, 2);

        const cookieMatch = document.cookie.match(/django_language=([^;]+)/);
        if (cookieMatch) return cookieMatch[1].toLowerCase().slice(0, 2);

        return "uz";
    }

    const lang = getLang();

    /* =====================================================
       TARJIMA LUG'ATI
       ===================================================== */

    const dict = {
        uz: {
            "Home": "Bosh sahifa",
            "Dashboard": "Boshqaruv paneli",
            "History": "Tarix",
            "Change history": "O'zgarishlar tarixi",
            "This object doesn't have a change history. It probably wasn't added via this admin site.":
                "Bu obyekt uchun o'zgarishlar tarixi mavjud emas. Ehtimol, u admin panel orqali qo'shilmagan.",
            "Save": "Saqlash",
            "Save and add another": "Saqlash va yana qo'shish",
            "Save and continue editing": "Saqlash va tahrirlashda davom etish",
            "Add": "Qo'shish",
            "Change": "O'zgartirish",
            "Delete": "O'chirish",
            "Search": "Qidirish",
            "Go": "Bajarish",
            "Select": "Tanlang",
            "Action": "Amal",
            "Recent actions": "So'nggi harakatlar",
            "My actions": "Mening harakatlarim",
            "None available": "Mavjud emas",
            "Filter": "Filtr",
            "Clear all filters": "Barcha filtrlarni tozalash",
            "Yes": "Ha",
            "No": "Yo'q",
            "Are you sure?": "Ishonchingiz komilmi?",
            "Please correct the error below.": "Quyidagi xatoni to'g'irlang.",
            "Please correct the errors below.": "Quyidagi xatolarni to'g'irlang.",
            "Add another": "Yana qo'shish",
            "Remove": "O'chirish",
            "Today": "Bugun",
            "Now": "Hozir",
            "Choose a date": "Sana tanlang",
            "Choose a time": "Vaqt tanlang",
        },
        ru: {
            "Home": "Главная",
            "Dashboard": "Панель управления",
            "History": "История",
            "Change history": "История изменений",
            "This object doesn't have a change history. It probably wasn't added via this admin site.":
                "У этого объекта нет истории изменений. Возможно, он был добавлен не через административную панель.",
            "Save": "Сохранить",
            "Save and add another": "Сохранить и добавить ещё",
            "Save and continue editing": "Сохранить и продолжить редактирование",
            "Add": "Добавить",
            "Change": "Изменить",
            "Delete": "Удалить",
            "Search": "Поиск",
            "Go": "Выполнить",
            "Select": "Выбрать",
            "Action": "Действие",
            "Recent actions": "Последние действия",
            "My actions": "Мои действия",
            "None available": "Нет данных",
            "Filter": "Фильтр",
            "Clear all filters": "Очистить все фильтры",
            "Yes": "Да",
            "No": "Нет",
            "Are you sure?": "Вы уверены?",
            "Please correct the error below.": "Пожалуйста, исправьте ошибку ниже.",
            "Please correct the errors below.": "Пожалуйста, исправьте ошибки ниже.",
            "Add another": "Добавить ещё",
            "Remove": "Удалить",
            "Today": "Сегодня",
            "Now": "Сейчас",
            "Choose a date": "Выберите дату",
            "Choose a time": "Выберите время",
        },
        en: {}
    };

    /* =====================================================
       1. TEMA TUGMASINI O'CHIRISH
       ===================================================== */

    function removeThemeButton() {
        document.querySelectorAll("#theme-toggle-btn, .vet-theme-nav-item").forEach(function (el) {
            el.remove();
        });
        document.body.classList.remove("admin-theme-dark", "admin-theme-light");
        localStorage.removeItem("vet_admin_theme");
    }

    /* =====================================================
       2. TARJIMA
       ===================================================== */

    function translatePage() {
        const translations = dict[lang] || dict.uz;
        if (lang === "en") return;

        const walker = document.createTreeWalker(
            document.body,
            NodeFilter.SHOW_TEXT,
            {
                acceptNode: function (node) {
                    const parent = node.parentElement;
                    if (!parent) return NodeFilter.FILTER_REJECT;
                    const tag = parent.tagName;
                    if (["SCRIPT", "STYLE", "TEXTAREA", "CODE", "PRE"].includes(tag)) {
                        return NodeFilter.FILTER_REJECT;
                    }
                    return NodeFilter.FILTER_ACCEPT;
                }
            }
        );

        let node;
        while ((node = walker.nextNode())) {
            const text = node.nodeValue.trim();
            if (!text || text.length > 200) continue;
            if (translations[text]) {
                node.nodeValue = node.nodeValue.replace(text, translations[text]);
            }
        }

        document.querySelectorAll("input, button").forEach(function (el) {
            if (el.value && translations[el.value]) {
                el.value = translations[el.value];
            }
            const btnText = el.textContent.trim();
            if (btnText && translations[btnText]) {
                el.textContent = translations[btnText];
            }
            if (el.title && translations[el.title]) {
                el.title = translations[el.title];
            }
        });

        document.querySelectorAll("[placeholder]").forEach(function (el) {
            const ph = el.getAttribute("placeholder");
            if (ph && translations[ph]) {
                el.setAttribute("placeholder", translations[ph]);
            }
        });
    }

    /* =====================================================
       3. DASHBOARD — O'ZGARTIRISH TUGMASINI YASHIRISH
       ===================================================== */

    function hideDashboardChangeButtons() {
        const path = window.location.pathname.replace(/\/+$/, "");
        if (path !== "/admin") return;

        const changeWords = [
            "O'zgartirish", "O'zgartirish",
            "Изменить", "Change"
        ];

        document.querySelectorAll("a, button").forEach(function (el) {
            const text = el.textContent.trim();
            const href = el.getAttribute("href") || "";
            const isChangeText = changeWords.includes(text);
            const isChangeHref = href.includes("/change/");
            const isAddHref = href.includes("/add/");

            if ((isChangeText || isChangeHref) && !isAddHref) {
                el.style.display = "none";
            }
        });
    }

    /* =====================================================
       4. SO'NGGI HARAKATLAR — SLIDING PANEL
       ===================================================== */

    function createRecentActionsPanel() {
        const path = window.location.pathname.replace(/\/+$/, "");
        if (path !== "/admin") return;
        if (document.querySelector(".vet-recent-panel")) return;

        const headings = Array.from(document.querySelectorAll("h2, h3, .card-title"));
        const recentHeading = headings.find(function (el) {
            const text = el.textContent.trim().toLowerCase();
            return (
                text.includes("so'nggi") ||
                text.includes("so\u2019nggi") ||
                text.includes("recent") ||
                text.includes("послед")
            );
        });

        if (!recentHeading) return;

        let recentBlock = recentHeading.closest(".card") || recentHeading.parentElement;
        let parent = recentBlock;

        for (let i = 0; i < 5; i++) {
            if (parent && parent.className && String(parent.className).includes("col")) {
                recentBlock = parent;
                break;
            }
            parent = parent ? parent.parentElement : null;
        }

        // Panel yaratish
        const panel = document.createElement("div");
        panel.className = "vet-recent-panel";
        panel.setAttribute("aria-label", "So'nggi harakatlar paneli");

        const inner = document.createElement("div");
        inner.innerHTML = recentBlock.innerHTML;
        panel.appendChild(inner);

        // Toggle tugmasi
        const toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "vet-recent-toggle";
        toggle.innerHTML = "&#8249;";
        toggle.setAttribute("aria-label", "So'nggi harakatlar panelini ochish/yopish");
        toggle.title = "So'nggi harakatlar";

        document.body.appendChild(panel);
        document.body.appendChild(toggle);

        recentBlock.style.display = "none";

        let isOpen = false;

        toggle.addEventListener("click", function () {
            isOpen = !isOpen;
            panel.classList.toggle("open", isOpen);
            toggle.innerHTML = isOpen ? "&#8250;" : "&#8249;";
            toggle.setAttribute("aria-expanded", isOpen.toString());
        });

        // Panel tashqarisiga click qilganda yopish
        document.addEventListener("click", function (e) {
            if (
                isOpen &&
                !panel.contains(e.target) &&
                !toggle.contains(e.target)
            ) {
                isOpen = false;
                panel.classList.remove("open");
                toggle.innerHTML = "&#8249;";
                toggle.setAttribute("aria-expanded", "false");
            }
        });

        // Escape tugmasi bilan yopish
        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape" && isOpen) {
                isOpen = false;
                panel.classList.remove("open");
                toggle.innerHTML = "&#8249;";
                toggle.setAttribute("aria-expanded", "false");
                toggle.focus();
            }
        });
    }

    /* =====================================================
       5. SELECT2 FIX
       ===================================================== */

    function fixSelect2() {
        document.querySelectorAll(".select2-container").forEach(function (el) {
            if (!el.classList.contains("vet-select2")) {
                el.classList.add("vet-select2");
            }
        });
    }

    /* =====================================================
       6. JADVAL QATORLARINI ANIMATSIYA BILAN CHIQARISH
       ===================================================== */

    function animateTableRows() {
        const rows = document.querySelectorAll("#result_list tbody tr, .table tbody tr");
        rows.forEach(function (row, index) {
            row.style.opacity = "0";
            row.style.transform = "translateY(10px)";
            row.style.transition = "opacity 0.3s ease, transform 0.3s ease";
            setTimeout(function () {
                row.style.opacity = "1";
                row.style.transform = "translateY(0)";
            }, 40 * index);
        });
    }

    /* =====================================================
       7. ACTIVE LINK BELGILASH (sidebar uchun)
       ===================================================== */

    function markActiveLinks() {
        const currentPath = window.location.pathname;
        document.querySelectorAll(".nav-sidebar .nav-link").forEach(function (link) {
            const href = link.getAttribute("href");
            if (href && currentPath.startsWith(href) && href !== "/admin/") {
                link.classList.add("active");
            }
        });
    }

    /* =====================================================
       8. TOOLTIP QISQARTIRISH (uzun matnlar uchun)
       ===================================================== */

    function addTooltipsForLongText() {
        document.querySelectorAll("td, .breadcrumb-item").forEach(function (el) {
            if (el.scrollWidth > el.clientWidth + 5 && !el.title) {
                el.title = el.textContent.trim();
                el.style.overflow = "hidden";
                el.style.textOverflow = "ellipsis";
                el.style.whiteSpace = "nowrap";
            }
        });
    }

    /* =====================================================
       BOSH FUNKSIYA
       ===================================================== */

    function runAll() {
        removeThemeButton();
        translatePage();
        hideDashboardChangeButtons();
        createRecentActionsPanel();
        fixSelect2();
        markActiveLinks();
    }

    function runAfterRender() {
        animateTableRows();
        addTooltipsForLongText();
    }

    function boot() {
        runAll();
        runAfterRender();

        // Dinamik o'zgarishlar uchun kechiktirilgan ishga tushirish
        setTimeout(runAll, 350);
        setTimeout(function () {
            runAll();
            runAfterRender();
        }, 900);

        // MutationObserver — Ajax yoki dinamik DOM o'zgarishlari
        const observer = new MutationObserver(function (mutations) {
            let significant = mutations.some(function (m) {
                return m.addedNodes.length > 0;
            });
            if (significant) {
                hideDashboardChangeButtons();
                fixSelect2();
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    /* =====================================================
       ISHGA TUSHIRISH
       ===================================================== */

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot);
    } else {
        boot();
    }

})();