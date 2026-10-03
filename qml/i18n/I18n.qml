pragma Singleton
import QtQuick
import "translations.js" as Catalogs

QtObject {
    id: root

    // Supported languages are intentionally limited to the two requested by the project.
    property string language: "en"

    readonly property var catalog: language === "en" ? Catalogs.en : Catalogs.pl

    function t(key) {
        const current = root.catalog
        if (current && current[key] !== undefined)
            return current[key]
        if (Catalogs.pl && Catalogs.pl[key] !== undefined)
            return Catalogs.pl[key]
        return key
    }

    function pluralForm(count) {
        const n = Math.abs(Number(count) || 0)
        if (root.language === "pl") {
            if (n === 1) return "one"
            if (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20)) return "few"
            return "many"
        }
        return n === 1 ? "one" : "other"
    }

    function format(key, values) {
        let text = root.t(key)
        if (!values)
            return text

        // QVariant maps arriving from Python are not guaranteed to be
        // enumerable with `for ... in` in every Qt/QML binding path.
        // Extract placeholders from the translated text and read the
        // corresponding values explicitly so `{count}`, `{name}`, etc.
        // are always interpolated.
        const matches = text.match(/\{([A-Za-z0-9_.-]+)\}/g) || []
        const names = {}
        for (let i = 0; i < matches.length; i++) {
            const token = matches[i]
            const name = token.slice(1, -1)
            if (names[name])
                continue
            names[name] = true
            let value
            try { value = values[name] } catch (e) { value = undefined }
            if (value !== undefined && value !== null) {
                const stringValue = String(value)
                const replacement = stringValue.startsWith("__I18N__:")
                    ? root.resolveMessage(stringValue)
                    : stringValue
                text = text.split(token).join(replacement)
            }
        }
        return text
    }

    function resolveMessage(message) {
        let raw = String(message || "")
        for (let depth = 0; depth < 8 && raw.startsWith("__I18N__:"); depth++) {
            const payload = raw.slice("__I18N__:".length)
            const separator = payload.indexOf("|")
            const key = separator >= 0 ? payload.slice(0, separator) : payload
            let values = {}
            if (separator >= 0) {
                try { values = JSON.parse(payload.slice(separator + 1)) || {} }
                catch (e) { values = {} }
            }
            if (key === "date.absolute") {
                raw = root.format("date.absolute", {
                    day: values.day,
                    month: root.t("date.month." + Number(values.month)),
                    year: values.year,
                })
            } else if (key === "date.relative") {
                const kind = String(values.kind || "unknown")
                const count = Number(values.count || 0)
                if (kind === "now" || kind === "unknown")
                    raw = root.t("date.relative." + kind)
                else {
                    const form = root.pluralForm(count)
                    const suffix = kind === "minutes" ? "" : "." + form
                    raw = root.format("date.relative." + kind + suffix, {count: count})
                }
            } else {
                raw = root.format(key, values)
            }
        }
        return raw
    }

    function languageChangedToast() {
        return root.t(root.language === "en"
            ? "settings.languageChanged.en"
            : "settings.languageChanged.pl")
    }
}
