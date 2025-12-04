// Strip "libb." prefix from autosummary table entries on index page
document.addEventListener('DOMContentLoaded', function() {
    // Only run on the index page
    if (!window.location.pathname.endsWith('index.html') &&
        !window.location.pathname.endsWith('/')) {
        return;
    }

    // Find all autosummary table links
    const links = document.querySelectorAll('.autosummary td:first-child a');

    links.forEach(function(link) {
        const text = link.textContent;
        if (text.startsWith('libb.')) {
            link.textContent = text.substring(5);  // Remove "libb." (5 chars)
        }
    });
});
