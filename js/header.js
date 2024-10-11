
export default function addNavHamburgerListener() {
    document.querySelector('.mobile-nav-bars').addEventListener('click', function () {
        const mainNav = document.querySelector('.main-nav')
        if (!mainNav.classList.contains('mobile-open')) {
            mainNav.classList.add('mobile-open')
            mainNav.classList.remove('mobile-closed')
        } else {
            mainNav.classList.add('mobile-closed')
            mainNav.classList.remove('mobile-open')
        }
    })
}