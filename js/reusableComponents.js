class OurHeader extends HTMLElement {
    connectedCallback() {
        this.innerHTML = `
            <nav class="main-nav" aria-label="Main Navigation">
                <div class="navbar dark-mode">
                    <div class="nav-primary" aria-label="Primary pages">
                        <a href="/#main">Home</a>
                        <a href="/platform.html">Platform</a>
                        <a href="/calendar.html?city=baltimore">Calendar</a>
                        <a href="/projects.html">Projects</a>
                    </div>
                    <div class="nav-actions" aria-label="Account and support">
                        <a
                            id="portal-login-button"
                            class="nav-login-button"
                            href="/p/"
                            data-pidp-base="https://id.codecollective.us"
                            aria-label="Log in to the portal"
                        >Login</a>
                    </div>
                </div>
            </nav>
        `
    }
}

class OurFooter extends HTMLElement {
    connectedCallback() {
        this.innerHTML = `
            <footer id="footer">
                <ul class="copyright">
                    <li>&copy; Code Collective 2025</li>
                </ul>
            </footer>
        `
    }
}

class OurSocials extends HTMLElement {
    connectedCallback() {
        this.innerHTML = `
            <aside id="socialButtons" class="social__container">
                <a
                    href="https://matrix.to/#/#code-collective:matrix.org"
                    target="_blank"
                    class="social__link"
                >
                    <button class="social__button">
                        <img
                            src="/images/element_logo.svg"
                            alt="Matrix icon"
                            class="social__icon"
                        />
                    </button>
                </a>
                <a
                    href="https://chat.whatsapp.com/JFlI9aRvNaGCTU2lOFXpOt"
                    target="_blank"
                    class="social__link"
                >
                    <button class="social__button">
                        <img
                            src="/images/WhatsApp.svg.webp"
                            alt="WhatsApp icon"
                            class="social__icon"
                        />
                    </button>
                </a>
                <a
                    href="https://github.com/juliancoy/codecollective"
                    target="_blank"
                    class="social__link"
                >
                    <button class="social__button">
                        <img
                            src="/images/github_icon.png"
                            alt="GitHub icon"
                            class="social__icon"
                        />
                    </button>
                </a>
                <a
                    href="https://t.me/codecollective"
                    target="_blank"
                    class="social__link"
                >
                    <button class="social__button">
                        <img
                            src="/images/Telegram_logo.svg"
                            alt="Telegram icon"
                            class="social__icon"
                        />
                    </button>
                </a>
                <a
                    href="https://www.facebook.com/groups/687416533909466/"
                    target="_blank"
                    class="social__link"
                >
                    <button class="social__button">
                        <img
                            src="/images/Facebook_f_logo.svg"
                            alt="Facebook icon"
                            class="social__icon"
                        />
                    </button>
                </a>
                <a
                    href="https://discord.gg/ZSRhJmJmnN"
                    target="_blank"
                    class="social__link"
                >
                    <button class="social__button">
                        <img
                            src="/images/discord.jpg"
                            alt="Discord icon"
                            class="social__icon"
                        />
                    </button>
                </a>
                <a
                    href="https://luma.com/codecollective"
                    target="_blank"
                    class="social__link"
                >
                    <button class="social__button">
                        <img
                            src="/images/luma_icon.jpg"
                            alt="Luma icon"
                            class="social__icon"
                        />
                    </button>
                </a>
            </aside>
        `;
    }
}

class CalendarLegend extends HTMLElement {
    connectedCallback() {
        this.innerHTML = `
            <aside class="calendar-legend" aria-label="Event category filters">
                <div class="legend-title">Filter by lenses:</div>
                <div class="legend-items" id="calendar-legend-items"></div>
            </aside>
            <button type="button" id="legend-visibility-toggle" class="legend-toggle-button" aria-expanded="true">
                Show legend
            </button>
        `;
    }
}

const STANDARD_NAV_LINKS = [
    { href: '/#main', label: 'Home' },
    { href: '/platform.html', label: 'Platform' },
    { href: '/calendar.html?city=baltimore', label: 'Calendar' },
    { href: '/projects.html', label: 'Projects' },
    {
        href: '/p/',
        label: 'Login',
        id: 'portal-login-button',
        className: 'nav-login-button',
        ariaLabel: 'Log in to the portal',
        pidpBase: 'https://id.codecollective.us',
    },
];

const NAV_ACTION_LABELS = new Set(['login']);

function createDonateShortcut() {
    const link = document.createElement('a');
    link.href = '/donate.html';
    link.className = 'donate-shortcut';
    link.setAttribute('aria-label', 'Donate');
    link.title = 'Donate';
    link.innerHTML = `
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="M12 21s-6.716-4.35-9.193-8.19C1.066 10.113 1.62 6.7 4.61 5.18c2.034-1.035 4.358-.33 5.74 1.346C11.733 4.85 14.057 4.145 16.09 5.18c2.99 1.52 3.544 4.933 1.803 7.63C18.716 16.65 12 21 12 21Z"></path>
        </svg>
    `;
    return link;
}

function applyNavItemAttributes(link, item) {
    link.href = item.href;
    link.textContent = item.label;

    if (item.id) {
        link.id = item.id;
    } else if (link.id === 'portal-login-button') {
        link.removeAttribute('id');
    }

    if (item.className) {
        link.className = item.className;
    } else if (link.classList.contains('nav-login-button')) {
        link.classList.remove('nav-login-button');
    }

    if (item.ariaLabel) {
        link.setAttribute('aria-label', item.ariaLabel);
    } else {
        link.removeAttribute('aria-label');
    }

    if (item.pidpBase) {
        link.setAttribute('data-pidp-base', item.pidpBase);
    } else {
        link.removeAttribute('data-pidp-base');
    }
}

function configurePortalLogin() {
    const loginButtons = document.querySelectorAll('#portal-login-button, .nav-login-button[data-pidp-base]');

    loginButtons.forEach((loginButton) => {
        const pidpBase = loginButton.getAttribute('data-pidp-base') || 'https://id.codecollective.us';
        const nextUrl = `${window.location.origin}/p/constituent/dashboard`;
        const loginUrl = `${pidpBase.replace(/\/+$/, '')}/app/login?next=${encodeURIComponent(nextUrl)}`;
        loginButton.setAttribute('href', loginUrl);
        loginButton.setAttribute('aria-haspopup', 'dialog');
        loginButton.addEventListener('click', (event) => {
            if (loginButton.dataset.portalAuthenticated === 'true') {
                return;
            }
            event.preventDefault();
            openLoginModal(pidpBase, nextUrl, loginButton);
        });
    });
}

function normalizePidpAssetUrl(pidpBase, rawUrl) {
    if (!rawUrl) return null;
    if (/^(data:|https?:\/\/)/i.test(rawUrl)) return rawUrl;
    return `${pidpBase.replace(/\/+$/, '')}/${rawUrl.replace(/^\/+/, '')}`;
}

function userDisplayName(user) {
    return (
        user?.identity_data?.display_name?.trim() ||
        user?.full_name?.trim() ||
        user?.email ||
        'Account'
    );
}

function renderAuthenticatedNav(loginButton, user, pidpBase) {
    const displayName = userDisplayName(user);
    const avatarUrl = normalizePidpAssetUrl(pidpBase, user?.identity_data?.avatar_url || user?.avatar_url);
    const firstInitial = displayName.slice(0, 1).toUpperCase();

    loginButton.dataset.portalAuthenticated = 'true';
    loginButton.classList.remove('nav-login-button');
    loginButton.classList.add('nav-account-link');
    loginButton.href = '/p/constituent/dashboard';
    loginButton.removeAttribute('aria-haspopup');
    loginButton.setAttribute('aria-label', `${displayName} account`);
    loginButton.title = displayName;

    const avatar = document.createElement('span');
    avatar.className = 'nav-account-avatar';
    avatar.setAttribute('aria-hidden', 'true');

    if (avatarUrl) {
        const image = document.createElement('img');
        image.src = avatarUrl;
        image.alt = '';
        avatar.appendChild(image);
    } else {
        avatar.textContent = firstInitial;
    }

    loginButton.replaceChildren(avatar);
}

async function hydratePortalNavUser() {
    const loginButtons = document.querySelectorAll('#portal-login-button, .nav-login-button[data-pidp-base]');
    if (!loginButtons.length) return;

    const pidpBase = loginButtons[0].getAttribute('data-pidp-base') || 'https://id.codecollective.us';
    const base = pidpBase.replace(/\/+$/, '');

    try {
        const tokenResponse = await fetch(`${base}/auth/session-token`, {
            credentials: 'include',
        });
        if (!tokenResponse.ok) return;

        const tokenData = await tokenResponse.json();
        if (!tokenData?.access_token) return;

        const meResponse = await fetch(`${base}/auth/me`, {
            credentials: 'include',
            headers: {
                Authorization: `Bearer ${tokenData.access_token}`,
            },
        });
        if (!meResponse.ok) return;

        const user = await meResponse.json();
        loginButtons.forEach((loginButton) => renderAuthenticatedNav(loginButton, user, pidpBase));
    } catch {
        // Leave the login button unchanged when there is no readable PIdP session.
    }
}

function loginUrl(pidpBase, path, nextUrl) {
    const base = pidpBase.replace(/\/+$/, '');
    return `${base}${path}?next=${encodeURIComponent(nextUrl)}`;
}

function ensureLoginModal() {
    let modal = document.getElementById('login-choice-modal');
    if (modal) return modal;

    modal = document.createElement('div');
    modal.id = 'login-choice-modal';
    modal.className = 'login-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', 'login-choice-title');
    modal.hidden = true;
    modal.innerHTML = `
        <div class="login-modal__backdrop" data-login-modal-close></div>
        <section class="login-modal__panel" tabindex="-1">
            <div class="login-modal__header">
                <h2 id="login-choice-title">Log in</h2>
                <button class="login-modal__close" type="button" aria-label="Close login options" data-login-modal-close>&times;</button>
            </div>
            <div class="login-modal__options">
                <a class="login-modal__option" data-login-provider="google" href="#">Continue with Google</a>
                <a class="login-modal__option" data-login-provider="github" href="#">Continue with GitHub</a>
                <a class="login-modal__option login-modal__option--secondary" data-login-provider="password" href="#">Use email and password</a>
            </div>
        </section>
    `;
    document.body.appendChild(modal);
    modal.addEventListener('click', (event) => {
        if (event.target.closest('[data-login-modal-close]')) {
            closeLoginModal();
        }
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !modal.hidden) {
            closeLoginModal();
        }
    });
    return modal;
}

function openLoginModal(pidpBase, nextUrl, trigger) {
    const modal = ensureLoginModal();
    modal.querySelector('[data-login-provider="google"]').href = loginUrl(pidpBase, '/auth/google/login', nextUrl);
    modal.querySelector('[data-login-provider="github"]').href = loginUrl(pidpBase, '/auth/github/login', nextUrl);
    modal.querySelector('[data-login-provider="password"]').href = loginUrl(pidpBase, '/app/login', nextUrl);
    modal._loginTrigger = trigger;
    modal.hidden = false;
    document.body.classList.add('login-modal-open');
    requestAnimationFrame(() => {
        modal.querySelector('.login-modal__panel').focus();
    });
}

function closeLoginModal() {
    const modal = document.getElementById('login-choice-modal');
    if (!modal || modal.hidden) return;
    modal.hidden = true;
    document.body.classList.remove('login-modal-open');
    if (modal._loginTrigger) {
        modal._loginTrigger.focus();
    }
}

function normalizeMainNavs() {
    const navbars = document.querySelectorAll('.main-nav .navbar');

    navbars.forEach((navbar) => {
        if (navbar.dataset.navConsistent === 'skip') {
            return;
        }

        const existingPrimary = navbar.querySelector(':scope > .nav-primary');
        const existingActions = navbar.querySelector(':scope > .nav-actions');
        const sourceNodes = [
            ...Array.from(navbar.querySelectorAll(':scope > a')),
            ...Array.from(existingPrimary?.children || []),
            ...Array.from(existingActions?.children || []),
        ];
        const primary = existingPrimary || document.createElement('div');
        const actions = existingActions || document.createElement('div');
        primary.className = 'nav-primary';
        primary.setAttribute('aria-label', 'Primary pages');
        actions.className = 'nav-actions';
        actions.setAttribute('aria-label', 'Account and support');
        const primaryLinks = [];
        const actionLinks = [];

        STANDARD_NAV_LINKS.forEach((item) => {
            const existing = sourceNodes.find((link) => {
                const href = link.getAttribute('href') || '';
                const text = link.textContent.trim().toLowerCase();
                return href === item.href || text === item.label.toLowerCase() || (item.id && link.id === item.id);
            });

            if (existing) {
                applyNavItemAttributes(existing, item);
                if (NAV_ACTION_LABELS.has(item.label.toLowerCase())) actionLinks.push(existing);
                else primaryLinks.push(existing);
            } else {
                const link = document.createElement('a');
                applyNavItemAttributes(link, item);
                if (NAV_ACTION_LABELS.has(item.label.toLowerCase())) actionLinks.push(link);
                else primaryLinks.push(link);
            }
        });

        const extraNodes = sourceNodes.filter((node) => !primaryLinks.includes(node) && !actionLinks.includes(node) && !node.classList?.contains('donate-shortcut'));
        const donate = sourceNodes.find((node) => node.classList?.contains('donate-shortcut')) || createDonateShortcut();

        primary.replaceChildren(...primaryLinks, ...extraNodes);
        actions.replaceChildren(...actionLinks, donate);
        navbar.replaceChildren(primary, actions);
    });
}

function addDonateShortcut() {
    const navs = document.querySelectorAll('.main-nav');

    navs.forEach((nav) => {
        if (nav.dataset.hideDonate === 'true') {
            return;
        }

        const actions = nav.querySelector('.nav-actions');
        if (!actions || actions.querySelector('.donate-shortcut')) {
            return;
        }

        actions.appendChild(createDonateShortcut());
    });
}

customElements.define('our-header', OurHeader)
customElements.define('our-footer', OurFooter)
customElements.define('our-slack-link', OurSocials)
customElements.define('calendar-legend', CalendarLegend)

document.addEventListener('DOMContentLoaded', () => {
    normalizeMainNavs();
    configurePortalLogin();
    hydratePortalNavUser();
    addDonateShortcut();
});
