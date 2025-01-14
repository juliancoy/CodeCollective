function toggleDescription(button) {
    const description = button.previousElementSibling; // Get the description element
    if (description.classList.contains('collapsed')) {
        description.classList.remove('collapsed');
        description.classList.add('expanded');
        button.textContent = 'See less';
    } else {
        description.classList.remove('expanded');
        description.classList.add('collapsed');
        button.textContent = 'See more';
    }
}