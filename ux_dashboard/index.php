<?php
require_once 'db_config.php';

// --- Fetch summary stats ---
$total_conversations = $conn->query("SELECT COUNT(*) as count FROM conversations")->fetch_assoc()['count'];
$total_messages = $conn->query("SELECT COUNT(*) as count FROM messages")->fetch_assoc()['count'];

$sentiment_stats = $conn->query("
    SELECT sentiment_label, COUNT(*) as count 
    FROM messages 
    WHERE role='user' AND sentiment_label IS NOT NULL 
    GROUP BY sentiment_label
");
$sentiment_counts = ['positive' => 0, 'negative' => 0, 'neutral' => 0];
while ($row = $sentiment_stats->fetch_assoc()) {
    $sentiment_counts[$row['sentiment_label']] = $row['count'];
}

$avg_sentiment = $conn->query("
    SELECT AVG(sentiment_score) as avg_score 
    FROM messages 
    WHERE role='user' AND sentiment_score IS NOT NULL
")->fetch_assoc()['avg_score'];
$avg_sentiment = round($avg_sentiment ?: 0, 2);

// --- Conversations list with rating (derived from sentiment) ---
$conversations = $conn->query("
    SELECT c.id, c.title, c.created_at, 
           (SELECT AVG(sentiment_score) FROM messages WHERE conversation_id = c.id AND role='user') as avg_score
    FROM conversations c
    ORDER BY c.created_at DESC
");
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mr Hero - UX Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background: #f4f6f9; }
        .card-stats { border-left: 4px solid #3498db; transition: 0.2s; }
        .card-stats:hover { transform: translateY(-3px); }
        .conversation-row { cursor: pointer; }
        .modal-lg-custom { max-width: 800px; }
        .badge-positive { background: #2ecc71; }
        .badge-negative { background: #e74c3c; }
        .badge-neutral { background: #95a5a6; }
    </style>
</head>
<body>
<div class="container-fluid py-4">
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h1><i class="bi bi-robot"></i> Mr Hero - UX Analytics Dashboard</h1>
        <div class="text-muted">Real‑time feedback insights</div>
    </div>

    <!-- Stats Cards -->
    <div class="row g-4 mb-4">
        <div class="col-md-3">
            <div class="card card-stats shadow-sm">
                <div class="card-body">
                    <h5 class="card-title text-muted">Total Conversations</h5>
                    <h2 class="display-6"><?= $total_conversations ?></h2>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card card-stats shadow-sm">
                <div class="card-body">
                    <h5 class="card-title text-muted">Total Messages</h5>
                    <h2 class="display-6"><?= $total_messages ?></h2>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card card-stats shadow-sm">
                <div class="card-body">
                    <h5 class="card-title text-muted">Avg Sentiment Score</h5>
                    <h2 class="display-6"><?= $avg_sentiment ?></h2>
                    <small>(from -1 to +1)</small>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card card-stats shadow-sm">
                <div class="card-body">
                    <h5 class="card-title text-muted">Sentiment Breakdown</h5>
                    <div class="d-flex justify-content-between">
                        <span><i class="bi bi-emoji-smile-fill text-success"></i> <?= $sentiment_counts['positive'] ?></span>
                        <span><i class="bi bi-emoji-frown-fill text-danger"></i> <?= $sentiment_counts['negative'] ?></span>
                        <span><i class="bi bi-emoji-neutral-fill text-secondary"></i> <?= $sentiment_counts['neutral'] ?></span>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="row g-4">
        <!-- Chart: Aspect Sentiments -->
        <div class="col-md-6">
            <div class="card shadow-sm">
                <div class="card-header bg-white">
                    <h5 class="mb-0"><i class="bi bi-bar-chart-steps"></i> Aspect‑Based Sentiment</h5>
                </div>
                <div class="card-body">
                    <canvas id="aspectChart" height="250"></canvas>
                </div>
            </div>
        </div>

        <!-- Recent Explicit Feedback -->
        <div class="col-md-6">
            <div class="card shadow-sm">
                <div class="card-header bg-white">
                    <h5 class="mb-0"><i class="bi bi-star-fill text-warning"></i> Latest Explicit Feedback</h5>
                </div>
                <div class="card-body p-0">
                    <table class="table table-sm mb-0">
                        <thead class="table-light"><tr><th>Rating</th><th>Comment</th><th>Date</th></tr></thead>
                        <tbody>
                        <?php
                        $explicit = $conn->query("
                            SELECT ef.rating, ef.comment, ef.timestamp, c.title as conv_title 
                            FROM explicit_feedback ef 
                            JOIN conversations c ON ef.conversation_id = c.id 
                            ORDER BY ef.timestamp DESC LIMIT 5
                        ");
                        while ($row = $explicit->fetch_assoc()):
                        ?>
                            <tr>
                                <td><span class="badge bg-warning text-dark"><?= $row['rating'] ?> ★</span></td>
                                <td><?= htmlspecialchars(substr($row['comment'] ?? '', 0, 50)) ?></td>
                                <td><?= date('d/m H:i', strtotime($row['timestamp'])) ?></td>
                            </tr>
                        <?php endwhile; ?>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <!-- Conversations Table -->
    <div class="card shadow-sm mt-4">
        <div class="card-header bg-white">
            <h5 class="mb-0"><i class="bi bi-chat-dots"></i> All Conversations</h5>
        </div>
        <div class="card-body p-0">
            <table class="table table-hover mb-0">
                <thead class="table-light">
                    <tr><th>Title</th><th>Created</th><th>Avg Rating (1-5)</th><th>Actions</th></tr>
                </thead>
                <tbody>
                <?php while ($conv = $conversations->fetch_assoc()): 
                    $avg_score = $conv['avg_score'];
                    $star_rating = $avg_score ? round((($avg_score + 1) / 2) * 4 + 1, 1) : 3.0;
                    $star_rating = max(1, min(5, $star_rating));
                ?>
                    <tr class="conversation-row" data-id="<?= $conv['id'] ?>" data-title="<?= htmlspecialchars($conv['title']) ?>">
                        <td><?= htmlspecialchars($conv['title']) ?></td>
                        <td><?= date('d M Y H:i', strtotime($conv['created_at'])) ?></td>
                        <td><?= $star_rating ?> ★</td>
                        <td><button class="btn btn-sm btn-outline-primary view-chat-btn" data-id="<?= $conv['id'] ?>"><i class="bi bi-eye"></i> View Chat</button></td>
                    </tr>
                <?php endwhile; ?>
                </tbody>
            </table>
        </div>
    </div>
</div>

<!-- Modal for Chat Messages -->
<div class="modal fade" id="chatModal" tabindex="-1">
    <div class="modal-dialog modal-lg-custom modal-dialog-centered">
        <div class="modal-content">
            <div class="modal-header bg-dark text-white">
                <h5 class="modal-title"><i class="bi bi-chat-text"></i> Conversation: <span id="modalConvTitle"></span></h5>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body" id="modalMessages" style="max-height: 60vh; overflow-y: auto;">
                Loading...
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
            </div>
        </div>
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
<script>
    // Aspect chart
    fetch('get_aspect_data.php')
        .then(res => res.json())
        .then(data => {
            const ctx = document.getElementById('aspectChart').getContext('2d');
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.aspects,
                    datasets: [
                        { label: 'Positive', data: data.positive, backgroundColor: '#2ecc71' },
                        { label: 'Negative', data: data.negative, backgroundColor: '#e74c3c' },
                        { label: 'Neutral', data: data.neutral, backgroundColor: '#95a5a6' }
                    ]
                },
                options: { responsive: true, scales: { x: { stacked: true }, y: { stacked: true } } }
            });
        });

    // Modal: load conversation messages
    const chatModal = new bootstrap.Modal(document.getElementById('chatModal'));
    document.querySelectorAll('.view-chat-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const convId = btn.getAttribute('data-id');
            const convTitle = btn.closest('tr').querySelector('td:first-child').innerText;
            document.getElementById('modalConvTitle').innerText = convTitle;
            document.getElementById('modalMessages').innerHTML = '<div class="text-center py-4"><div class="spinner-border text-primary"></div><p>Loading messages...</p></div>';
            chatModal.show();
            try {
                const res = await fetch(`get_messages.php?conversation_id=${convId}`);
                const html = await res.text();
                document.getElementById('modalMessages').innerHTML = html;
            } catch(e) {
                document.getElementById('modalMessages').innerHTML = '<div class="alert alert-danger">Failed to load messages.</div>';
            }
        });
    });
</script>
</body>
</html>