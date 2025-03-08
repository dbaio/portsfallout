document.addEventListener("DOMContentLoaded", function () {
    let toggleButton = document.getElementById("toggle-timezone");
    let toggleHeader = document.getElementById("toggle-timezone-header");
    let timezoneInfo = document.getElementById("timezone-info");
    let isLocalTime = false;

    function getUTCOffset() {
        let offsetMinutes = new Date().getTimezoneOffset();
        let offsetHours = Math.abs(offsetMinutes / 60);
        let sign = offsetMinutes > 0 ? "-" : "+";
        return `UTC${sign}${String(Math.floor(offsetHours)).padStart(2, "0")}`;
    }

    function formatDateTimeUTC(utcDateString) {
        let dateObj = new Date(utcDateString);
        let year = dateObj.getUTCFullYear();
        let month = String(dateObj.getUTCMonth() + 1).padStart(2, "0");
        let day = String(dateObj.getUTCDate()).padStart(2, "0");
        let hours = String(dateObj.getUTCHours()).padStart(2, "0");
        let minutes = String(dateObj.getUTCMinutes()).padStart(2, "0");

        return `${year}-${month}-${day} ${hours}:${minutes}`;
    }

    function formatDateTimeLocal(utcDateString) {
        let dateObj = new Date(utcDateString);
        let year = dateObj.getFullYear();
        let month = String(dateObj.getMonth() + 1).padStart(2, "0");
        let day = String(dateObj.getDate()).padStart(2, "0");
        let hours = String(dateObj.getHours()).padStart(2, "0");
        let minutes = String(dateObj.getMinutes()).padStart(2, "0");

        return `${year}-${month}-${day} ${hours}:${minutes}`;
    }

    function setCookie(name, value, days) {
        let expires = "";
        if (days) {
            let date = new Date();
            date.setTime(date.getTime() + days * 24 * 60 * 60 * 1000);
            expires = "; expires=" + date.toUTCString();
        }
        document.cookie = name + "=" + value + expires + "; path=/";
    }

    function deleteCookie(name) {
        document.cookie = name + "=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    }

    function getCookie(name) {
        let nameEQ = name + "=";
        let ca = document.cookie.split(";");
        for (let i = 0; i < ca.length; i++) {
            let c = ca[i].trim();
            if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
        }
        return null;
    }

    function updateTimes() {
        document.querySelectorAll(".utc-time").forEach(function (element) {
            let utcDateString = element.getAttribute("data-utc");

            if (isLocalTime) {
                element.textContent = formatDateTimeLocal(utcDateString);
                if (timezoneInfo) timezoneInfo.textContent = getUTCOffset();
                if (toggleHeader) {
                    toggleHeader.textContent = `date (${getUTCOffset()})`;
                    toggleHeader.title = "Click to switch back to UTC";
                }
                setCookie("timezonePreference", "local", 30);
            } else {
                element.textContent = formatDateTimeUTC(utcDateString);
                if (timezoneInfo) timezoneInfo.textContent = "UTC";
                if (toggleHeader) {
                    toggleHeader.textContent = "date (UTC)";
                    toggleHeader.title = "Click to switch to your local timezone";
                }
                deleteCookie("timezonePreference");
            }
        });

        if (toggleButton) {
            toggleButton.textContent = isLocalTime ? "Switch to UTC" : "Switch to Local Time";
        }
    }

    let timezonePreference = getCookie("timezonePreference");
    isLocalTime = timezonePreference === "local";

    if (toggleButton) {
        toggleButton.addEventListener("click", function () {
            isLocalTime = !isLocalTime;
            updateTimes();
        });
    }

    if (toggleHeader) {
        toggleHeader.addEventListener("click", function (event) {
            event.preventDefault();
            isLocalTime = !isLocalTime;
            updateTimes();
        });
    }

    updateTimes();
});
