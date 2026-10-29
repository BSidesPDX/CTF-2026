<?php $page_title = 'Submit Design - Tangerine Printing'; ?>
<?php include 'header.php'; ?>

<style>
    form {
        max-width: 700px;
        margin: 40px auto;
        background: linear-gradient(to bottom, #f9f9f9 0%, white 100%);
        padding: 40px;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }

    form label {
        display: block;
        color: #333;
        font-weight: 600;
        margin-bottom: 8px;
        margin-top: 20px;
        font-size: 16px;
    }

    form input[type="text"],
    form input[type="email"],
    form input[type="url"],
    form textarea {
        width: 100%;
        padding: 12px;
        border: 1px solid #ddd;
        border-radius: 5px;
        font-size: 15px;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        background: white;
        box-sizing: border-box;
    }

    form input[type="text"]:focus,
    form input[type="email"]:focus,
    form input[type="url"]:focus,
    form textarea:focus {
        outline: none;
        border-color: #ff8c00;
        box-shadow: 0 0 5px rgba(255,140,0,0.3);
    }

    form textarea {
        resize: vertical;
    }

    form input[type="submit"] {
        margin-top: 30px;
        background: linear-gradient(to bottom, #ff8c00 0%, #ff7700 100%);
        color: white;
        border: none;
        padding: 15px 50px;
        font-size: 18px;
        font-weight: bold;
        border-radius: 5px;
        cursor: pointer;
        box-shadow: 0 4px 8px rgba(255,140,0,0.3);
    }

    .form-message {
        max-width: 700px;
        margin: 20px auto;
        padding: 20px;
        border-radius: 8px;
        font-size: 16px;
    }

    .form-message strong {
        font-size: 18px;
    }

    .form-message.error {
        background: #ffe6e6;
        border: 2px solid #ff4444;
        color: #cc0000;
    }

    .form-message.success {
        background: #e6ffe6;
        border: 2px solid #44ff44;
        color: #008800;
    }

    .form-message pre {
        background: #f5f5f5;
        padding: 15px;
        border-radius: 5px;
        overflow-x: auto;
        margin-top: 10px;
    }
</style>

<main>
    <h2 style="text-align: center; color: #ff8c00; font-size: 36px; margin-bottom: 20px;">Submit Your Design</h2>
    <p style="text-align: center; font-size: 18px; margin-bottom: 30px; color: #555;">Ready to get your project printed? Fill out the form below and upload your design file.</p>

    <?php
    if ($_SERVER['REQUEST_METHOD'] === 'POST') {
        $name = $_POST['name'] ?? '';
        $email = $_POST['email'] ?? '';
        $logo_url = $_POST['logo_url'] ?? '';
        $description = $_POST['description'] ?? '';

        if (empty($name) || empty($email) || empty($logo_url)) {
            echo '<div class="form-message error"><p><strong>Error:</strong> Please fill in all required fields.</p></div>';
        } else {
            // Download the file from the URL
            $context = stream_context_create([
                'http' => [
                    'timeout' => 5,
                    'follow_location' => 1
                ]
            ]);

            $file_content = @file_get_contents($logo_url, false, $context);

            if ($file_content === false) {
                echo '<div class="form-message error"><p><strong>Error:</strong> We could not download the URL you sent us. Please make sure it\'s a valid Photoshop document.</p></div>';
            } else {
                // Check mime type using finfo
                $finfo = new finfo(FILEINFO_MIME_TYPE);
                $mime_type = $finfo->buffer($file_content);

                if ($mime_type !== 'image/vnd.adobe.photoshop') {
                    echo '<div class="form-message error">';
                    echo '<p><strong>Error:</strong> We could not download the URL you sent us. Please make sure it\'s a valid Photoshop document.</p>';
                    echo '<p>Response data:</p>';
                    echo '<pre>' . htmlspecialchars($file_content) . '</pre>';
                    echo '</div>';
                } else {
                    echo '<div class="form-message success"><p><strong>Success!</strong> Thank you for your submission! We will review your logo design and get back to you soon.</p></div>';
                }
            }
        }
    }
    ?>

    <form method="POST" action="">
        <label for="name">Your Name:</label>
        <input type="text" id="name" name="name" required placeholder="John Designer">

        <label for="email">Your Email Address:</label>
        <input type="email" id="email" name="email" required placeholder="you@example.com">

        <!-- Validation for file type handled in PHP after downloading file -->

        <label for="logo_url">URL of Your Logo Design:</label>
        <input type="url" id="logo_url" name="logo_url" required placeholder="https://example.com/logo.psd">

        <label for="description">Design Requirements:</label>
        <textarea id="description" name="description" rows="10" placeholder="Specify sizing, margins, and other requirements..."></textarea>

        <input type="submit" value="Submit Design">
    </form>
</main>

<?php include 'footer.php'; ?>
