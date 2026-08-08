// Theme preference, stored the same way as the timezone one: a cookie read on
// the next visit. Applied to <html> before paint by the inline snippet in
// base.html, so the page never flashes the wrong theme.

(function () {
    "use strict";

    var COOKIE = "themePreference";

    function setCookie(name, value, days) {
        var expires = "";
        if (days) {
            var date = new Date();
            date.setTime(date.getTime() + days * 24 * 60 * 60 * 1000);
            expires = "; expires=" + date.toUTCString();
        }
        document.cookie = name + "=" + value + expires + "; path=/; SameSite=Lax";
    }

    function deleteCookie(name) {
        document.cookie = name + "=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    }

    function getCookie(name) {
        var nameEQ = name + "=";
        var parts = document.cookie.split(";");
        for (var i = 0; i < parts.length; i++) {
            var part = parts[i].trim();
            if (part.indexOf(nameEQ) === 0) {
                return part.substring(nameEQ.length);
            }
        }
        return null;
    }

    function systemTheme() {
        return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }

    // Three states, cycled in this order: follow the system, force light,
    // force dark. "system" removes the cookie and the attribute.
    var ORDER = ["system", "light", "dark"];
    var LABEL = { system: "auto", light: "light", dark: "dark" };
    var TITLE = {
        system: "Theme: following your system. Click to force light.",
        light: "Theme: light. Click to force dark.",
        dark: "Theme: dark. Click to follow your system."
    };

    function apply(theme, button) {
        if (theme === "system") {
            document.documentElement.removeAttribute("data-theme");
            deleteCookie(COOKIE);
        } else {
            document.documentElement.setAttribute("data-theme", theme);
            setCookie(COOKIE, theme, 365);
        }

        if (button) {
            button.textContent = LABEL[theme];
            button.title = TITLE[theme];
            button.setAttribute("aria-label", TITLE[theme]);
            var effective = theme === "system" ? systemTheme() : theme;
            button.setAttribute("aria-pressed", effective === "dark" ? "true" : "false");
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        var button = document.getElementById("theme-toggle");
        if (!button) {
            return;
        }

        var stored = getCookie(COOKIE);
        var current = ORDER.indexOf(stored) === -1 ? "system" : stored;
        apply(current, button);

        button.addEventListener("click", function () {
            current = ORDER[(ORDER.indexOf(current) + 1) % ORDER.length];
            apply(current, button);
        });
    });
})();
