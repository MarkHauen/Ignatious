(() => {
    const storageKey = 'ignatious-theme';
    const themes = ['light', 'dark', 'cyber-green'];
    const systemTheme = matchMedia('(prefers-color-scheme: dark)');
    let preference;
    let selector;

    function readPreference() {
        try { return localStorage.getItem(storageKey); } catch { return null; }
    }

    function applyTheme(value) {
        preference = themes.includes(value) ? value : null;
        const theme = preference || (systemTheme.matches ? 'dark' : 'light');
        document.documentElement.dataset.theme = theme;
        if (selector) selector.value = theme;
    }

    applyTheme(readPreference());
    systemTheme.addEventListener('change', () => {
        if (!preference) applyTheme(null);
    });
    window.addEventListener('storage', event => {
        if (event.key === storageKey || event.key === null) applyTheme(readPreference());
    });

    document.addEventListener('DOMContentLoaded', () => {
        const header = document.querySelector('.topbar');
        if (!header) return;
        const control = document.createElement('label');
        control.className = 'theme-control';
        control.htmlFor = 'theme-select';
        control.append('Theme');
        selector = document.createElement('select');
        selector.id = 'theme-select';
        selector.title = 'Color theme';
        for (const [value, label] of [['light', 'Light'], ['dark', 'Dark'], ['cyber-green', 'Cyber green']]) {
            selector.add(new Option(label, value));
        }
        selector.value = document.documentElement.dataset.theme;
        selector.addEventListener('change', () => {
            applyTheme(selector.value);
            try { localStorage.setItem(storageKey, preference); } catch {}
        });
        control.append(selector);
        (header.querySelector('.topbar-actions') || header).append(control);
    });
})();