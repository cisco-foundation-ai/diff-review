// Comment form state
let currentCommentContext = null;

// Copy file path to clipboard
function copyFilePath(filePath, event) {
    event.stopPropagation();

    navigator.clipboard.writeText(filePath).then(() => {
        // Show brief feedback
        const target = event.target;
        const originalText = target.textContent;
        target.textContent = '✓ Copied!';
        target.style.color = '#3fb950';

        setTimeout(() => {
            target.textContent = originalText;
            target.style.color = '';
        }, 1000);
    }).catch(err => {
        console.error('Failed to copy:', err);
        alert('Failed to copy file path');
    });
}

// Toggle PR Review Section
function togglePRReview() {
    const section = document.getElementById('pr-review');
    const arrow = document.getElementById('pr-review-arrow');

    if (section.classList.contains('collapsed')) {
        section.classList.remove('collapsed');
        arrow.textContent = '▼';
    } else {
        section.classList.add('collapsed');
        arrow.textContent = '▶';
    }
}

// Scroll to category in files content area
function scrollToCategory(categoryId) {
    const category = document.getElementById('category-' + categoryId);
    const filesContent = document.getElementById('files-content');

    if (category && filesContent) {
        // Expand the category if it's collapsed
        const content = document.getElementById('content-' + categoryId);
        const toggle = document.getElementById('toggle-' + categoryId);
        if (content && content.classList.contains('collapsed')) {
            content.classList.remove('collapsed');
            toggle.classList.remove('collapsed');
        }

        // Scroll to the category with offset to show the full header
        // offsetTop gives us the distance from the top of files-content
        // Subtract 180px to leave breathing room at the top
        const scrollTarget = category.offsetTop - 200;
        filesContent.scrollTo({
            top: Math.max(0, scrollTarget),
            behavior: 'instant'
        });
    }
}

function showCommentForm(btn, event) {
    event.stopPropagation();

    // Hide any existing form
    hideCommentForm();

    const row = btn.closest('tr');
    const filePath = row.dataset.filePath;
    const line = parseInt(row.dataset.line);
    const side = row.dataset.side;

    currentCommentContext = {
        path: filePath,
        line: line,
        side: side,
        row: row,
        type: 'line'
    };

    // Create inline comment form row
    const formRow = document.createElement('tr');
    formRow.className = 'comment-form-row active';
    formRow.id = 'active-comment-form';

    const isLightMode = document.body.classList.contains('light-mode');
    const bgColor = isLightMode ? '#ffffff' : '#0d1117';
    const textColor = isLightMode ? '#24292f' : '#c9d1d9';
    const borderColor = isLightMode ? '#d0d7de' : '#30363d';
    const contextBg = isLightMode ? '#f6f8fa' : '#0d1117';

    formRow.innerHTML = `
        <td colspan="4">
            <div class="comment-form-container">
                <div style="display: flex; align-items: center; margin-bottom: 12px;">
                    <strong style="color: ${textColor};">Add a comment on line ${side === 'RIGHT' ? 'R' : 'L'}${line}</strong>
                </div>
                <div style="background: ${contextBg}; border: 1px solid ${borderColor}; border-radius: 4px; padding: 8px 12px; margin-bottom: 12px; font-size: 12px;">
                    <code style="color: ${isLightMode ? '#0969da' : '#79c0ff'};">${filePath}:${line}</code>
                </div>
                <textarea id="comment-body" placeholder="Leave a comment" style="width: 100%; min-height: 100px; background: ${bgColor}; color: ${textColor}; border: 1px solid ${borderColor}; border-radius: 6px; padding: 8px; font-family: inherit; font-size: 14px; resize: vertical; margin-bottom: 12px;"></textarea>
                <div style="display: flex; gap: 8px; align-items: center;">
                    <button onclick="submitComment()" style="background: ${isLightMode ? '#1f883d' : '#238636'}; color: #ffffff; border: none; border-radius: 6px; padding: 6px 16px; font-size: 14px; font-weight: 500; cursor: pointer;">Add review comment</button>
                    <button onclick="hideCommentForm()" style="background: transparent; color: ${textColor}; border: 1px solid ${borderColor}; border-radius: 6px; padding: 6px 16px; font-size: 14px; cursor: pointer;">Cancel</button>
                    <span id="comment-status" style="margin-left: 12px;"></span>
                </div>
            </div>
        </td>
    `;

    // Insert form row after current row
    row.parentNode.insertBefore(formRow, row.nextSibling);

    // Focus textarea
    document.getElementById('comment-body').focus();
}

function showGeneralCommentForm() {
    // Hide any existing inline form
    hideCommentForm();

    currentCommentContext = { type: 'general' };

    document.getElementById('comment-form-title').textContent = 'Review this pull request';
    document.getElementById('comment-context').style.display = 'none';

    // Update the action buttons to show review options
    const actionsDiv = document.querySelector('.comment-actions');
    actionsDiv.innerHTML = `
        <button onclick="submitReview('COMMENT')" class="btn-primary" style="background: #238636; color: #ffffff; border: none; border-radius: 6px; padding: 8px 16px; font-size: 14px; font-weight: 500; cursor: pointer;">Comment</button>
        <button onclick="submitReview('APPROVE')" class="btn-approve" style="background: transparent; color: #3fb950; border: 1px solid #3fb950; border-radius: 6px; padding: 8px 16px; font-size: 14px; font-weight: 500; cursor: pointer;">Approve</button>
        <button onclick="submitReview('REQUEST_CHANGES')" class="btn-request-changes" style="background: transparent; color: #f85149; border: 1px solid #f85149; border-radius: 6px; padding: 8px 16px; font-size: 14px; font-weight: 500; cursor: pointer;">Request changes</button>
        <button onclick="hideCommentForm()" class="btn-secondary" style="background: transparent; color: #c9d1d9; border: 1px solid #30363d; border-radius: 6px; padding: 8px 16px; font-size: 14px; cursor: pointer; margin-left: 12px;">Cancel</button>
    `;

    document.getElementById('comment-overlay').style.display = 'flex';
    document.getElementById('comment-body').focus();
}

function hideCommentForm() {
    // Remove inline form if exists
    const activeForm = document.getElementById('active-comment-form');
    if (activeForm) {
        activeForm.remove();
    }

    // Hide overlay form
    const overlay = document.getElementById('comment-overlay');
    if (overlay) {
        overlay.style.display = 'none';
        const overlayBody = overlay.querySelector('#comment-body');
        if (overlayBody) overlayBody.value = '';
        const overlayStatus = overlay.querySelector('#comment-status');
        if (overlayStatus) overlayStatus.innerHTML = '';
    }

    currentCommentContext = null;
}

async function submitComment() {
    if (!currentCommentContext) return;

    const body = document.getElementById('comment-body').value.trim();
    if (!body) {
        alert('Comment cannot be empty');
        return;
    }

    const statusDiv = document.getElementById('comment-status');
    statusDiv.innerHTML = '<span class="loading">⏳ Posting comment...</span>';

    // Build request payload
    const payload = {
        body: body
    };

    if (currentCommentContext.type === 'line') {
        payload.path = currentCommentContext.path;
        payload.line = currentCommentContext.line;
        payload.side = currentCommentContext.side;
    }

    try {
        const response = await fetch('/api/comment', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });

        const result = await response.json();

        if (response.ok && result.success) {
            statusDiv.innerHTML = `<span class="success">✅ Comment posted! <a href="${result.html_url}" target="github-pr">View on GitHub →</a></span>`;

            // Add visual indicator for line comments (clickable link to comment)
            if (currentCommentContext.type === 'line') {
                const indicator = document.createElement('a');
                indicator.href = result.html_url;
                indicator.target = 'github-pr';
                indicator.className = 'comment-indicator';
                indicator.title = 'View comment on GitHub';
                indicator.textContent = '💬';
                const lineNumCell = currentCommentContext.row.querySelector('.line-num.new-num, .line-num.old-num');
                if (lineNumCell) {
                    lineNumCell.appendChild(indicator);
                }
            }

            // Auto-close after 3 seconds
            setTimeout(hideCommentForm, 3000);
        } else {
            const errorMsg = result.error || 'Unknown error';
            statusDiv.innerHTML = `<span class="error">❌ Error: ${errorMsg}</span>`;
        }
    } catch (error) {
        statusDiv.innerHTML = `<span class="error">❌ Failed to post comment: ${error.message}</span>`;
    }
}

async function submitReview(reviewEvent) {
    if (!currentCommentContext || currentCommentContext.type !== 'general') return;

    const body = document.getElementById('comment-body').value.trim();

    // Validate: only REQUEST_CHANGES requires a comment
    if (!body && reviewEvent === 'REQUEST_CHANGES') {
        alert('Change request requires a comment');
        return;
    }

    const statusDiv = document.getElementById('comment-status');
    const reviewTypeText = reviewEvent === 'APPROVE' ? 'Approving' : reviewEvent === 'REQUEST_CHANGES' ? 'Requesting changes' : 'Commenting';
    statusDiv.innerHTML = `<span class="loading">⏳ ${reviewTypeText}...</span>`;

    const payload = {
        body: body || '',
        review_event: reviewEvent
    };

    try {
        const response = await fetch('/api/comment', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });

        const result = await response.json();

        if (response.ok && result.success) {
            const successText = reviewEvent === 'APPROVE' ? '✅ PR approved!' : reviewEvent === 'REQUEST_CHANGES' ? '✅ Changes requested!' : '✅ Comment posted!';
            statusDiv.innerHTML = `<span class="success">${successText} <a href="${result.html_url}" target="github-pr">View on GitHub →</a></span>`;

            // Auto-close after 3 seconds
            setTimeout(hideCommentForm, 3000);
        } else {
            const errorMsg = result.error || 'Unknown error';
            statusDiv.innerHTML = `<span class="error">❌ Error: ${errorMsg}</span>`;
        }
    } catch (error) {
        statusDiv.innerHTML = `<span class="error">❌ Failed to submit review: ${error.message}</span>`;
    }
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    const overlay = document.getElementById('comment-overlay');
    if (overlay && e.key === 'Escape' && overlay.style.display !== 'none') {
        hideCommentForm();
    }
});

// Existing toggle functions
function toggleCategory(id) {
    const content = document.getElementById('content-' + id);
    const toggle = document.getElementById('toggle-' + id);
    const summary = document.getElementById('summary-' + id);

    if (content.classList.contains('collapsed')) {
        content.classList.remove('collapsed');
        toggle.classList.remove('collapsed');
        if (summary) {
            summary.classList.remove('collapsed');
        }
    } else {
        content.classList.add('collapsed');
        toggle.classList.add('collapsed');
        if (summary) {
            summary.classList.add('collapsed');
        }
    }
}

function toggleSummary(id) {
    const summary = document.getElementById('summary-' + id);
    const arrow = document.getElementById('summary-arrow-' + id);
    const button = arrow.closest('.summary-toggle');
    const label = button.querySelector('span:last-child');

    if (summary.classList.contains('collapsed')) {
        summary.classList.remove('collapsed');
        arrow.textContent = '▼';
        if (label) label.textContent = 'Hide detailed analysis';
    } else {
        summary.classList.add('collapsed');
        arrow.textContent = '▶';
        if (label) label.textContent = 'Show detailed analysis';
    }
}

function toggleFile(fileId) {
    const diff = document.getElementById('diff-' + fileId);
    const toggle = document.getElementById('toggle-' + fileId);

    if (diff.classList.contains('collapsed')) {
        diff.classList.remove('collapsed');
        toggle.classList.remove('collapsed');
    } else {
        diff.classList.add('collapsed');
        toggle.classList.add('collapsed');
    }
}

function toggleMeta(fileId) {
    const meta = document.getElementById('meta-' + fileId);
    if (meta.classList.contains('collapsed')) {
        meta.classList.remove('collapsed');
    } else {
        meta.classList.add('collapsed');
    }
}

function toggleTheme() {
    const checkbox = document.getElementById('theme-toggle-checkbox');
    const body = document.body;

    if (checkbox.checked) {
        body.classList.add('light-mode');
        localStorage.setItem('theme', 'light');
    } else {
        body.classList.remove('light-mode');
        localStorage.setItem('theme', 'dark');
    }

    // Dynamically toggle syntax highlighting by re-running Prism
    if (typeof Prism !== 'undefined') {
        // Re-highlight all code blocks with current theme
        document.querySelectorAll('.diff-table').forEach(table => {
            const fileDiv = table.closest('.file');
            const language = fileDiv ? fileDiv.dataset.language : '';

            if (language && Prism.languages[language]) {
                table.querySelectorAll('.line-content').forEach(cell => {
                    const spans = cell.querySelectorAll('.diff-add, .diff-del, .diff-ctx');
                    spans.forEach(span => {
                        const text = span.textContent;
                        if (text && text.trim()) {
                            try {
                                const highlighted = Prism.highlight(text, Prism.languages[language], language);
                                const tempDiv = document.createElement('div');
                                tempDiv.innerHTML = highlighted;
                                span.innerHTML = tempDiv.innerHTML;
                            } catch (e) {
                                console.warn('Prism highlighting failed:', e);
                            }
                        }
                    });
                });
            }
        });
    }
}

function toggleFormatting() {
    const checkbox = document.getElementById('formatting-toggle-checkbox');
    const body = document.body;

    if (checkbox.checked) {
        body.classList.add('hide-formatting');
        localStorage.setItem('hideFormatting', 'true');
    } else {
        body.classList.remove('hide-formatting');
        localStorage.setItem('hideFormatting', 'false');
    }
}

// Initialize theme from localStorage
(function() {
    const savedTheme = localStorage.getItem('theme');
    const checkbox = document.getElementById('theme-toggle-checkbox');

    if (savedTheme === 'light') {
        document.body.classList.add('light-mode');
        checkbox.checked = true;
    }
})();

// Initialize formatting toggle from localStorage
(function() {
    const hideFormatting = localStorage.getItem('hideFormatting');
    const checkbox = document.getElementById('formatting-toggle-checkbox');

    // Default to hiding formatting changes (checked by default in HTML)
    if (hideFormatting === null || hideFormatting === 'true') {
        document.body.classList.add('hide-formatting');
        checkbox.checked = true;

        // Auto-collapse formatting-only files on initial load
        document.querySelectorAll('.file.formatting-only').forEach(file => {
            const fileId = file.querySelector('.file-diff').id.replace('diff-', '');
            const diff = document.getElementById('diff-' + fileId);
            const toggle = document.getElementById('toggle-' + fileId);

            if (diff && toggle && !diff.classList.contains('collapsed')) {
                diff.classList.add('collapsed');
                toggle.classList.add('collapsed');
            }
        });
    } else {
        document.body.classList.remove('hide-formatting');
        checkbox.checked = false;
    }
})();

// Track visible categories and files
document.addEventListener('DOMContentLoaded', function() {
    const categories = document.querySelectorAll('.category');
    const files = document.querySelectorAll('.file');

    // Add click-to-collapse on category headers when sticky
    const categoryHeaders = document.querySelectorAll('.category-header');
    categoryHeaders.forEach((header) => {
        // Make the entire header clickable but preserve the toggle functionality
        header.style.cursor = 'pointer';
    });

    // Intersection Observer for tracking visible elements
    const observerOptions = {
        root: null,
        rootMargin: '-80px 0px -80% 0px',
        threshold: 0
    };

    let currentCategory = null;
    let currentFile = null;

    const categoryObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const categoryName = entry.target.dataset.categoryName;
                if (categoryName) {
                    currentCategory = categoryName;
                    updateBreadcrumb();
                }
            }
        });
    }, observerOptions);

    const fileObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const filePath = entry.target.dataset.filePath;
                if (filePath) {
                    currentFile = filePath;
                    updateBreadcrumb();
                }
            }
        });
    }, observerOptions);

    function updateBreadcrumb() {
        // This function can be used to update a breadcrumb if we add one
        // For now, it just tracks the current position
        // Debug: console.log('Current:', currentCategory, '>', currentFile);
    }

    categories.forEach(cat => categoryObserver.observe(cat));
    files.forEach(file => fileObserver.observe(file));

    // Apply Prism syntax highlighting to diff content
    if (typeof Prism !== 'undefined') {
        document.querySelectorAll('.diff-table').forEach(table => {
            // Get language from parent file element
            const fileDiv = table.closest('.file');
            const language = fileDiv ? fileDiv.dataset.language : '';

            if (language && Prism.languages[language]) {
                // Apply syntax highlighting to each line's content
                table.querySelectorAll('.line-content').forEach(cell => {
                    const spans = cell.querySelectorAll('.diff-add, .diff-del, .diff-ctx');
                    spans.forEach(span => {
                        const text = span.textContent;
                        if (text && text.trim()) {
                            try {
                                const highlighted = Prism.highlight(text, Prism.languages[language], language);
                                // Preserve the original class and wrap in a span with highlighted content
                                const tempDiv = document.createElement('div');
                                tempDiv.innerHTML = highlighted;
                                span.innerHTML = tempDiv.innerHTML;
                            } catch (e) {
                                // If highlighting fails, keep original text
                                console.warn('Prism highlighting failed:', e);
                            }
                        }
                    });
                });
            }
        });
    }
});
