<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?php echo isset($page_title) ? $page_title : 'Tangerine Printing'; ?></title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f5f5;
            color: #333;
            line-height: 1.6;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
        }

        /* Header Styles */
        header {
            background: linear-gradient(to bottom, #fff 0%, #f0f0f0 100%);
            border-bottom: 3px solid #ff8c00;
            padding: 20px 0;
        }

        header .container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: relative;
        }

        header h1 {
            color: #ff8c00;
            font-size: 32px;
            display: flex;
            align-items: center;
            gap: 15px;
        }

        nav {
            display: flex;
            gap: 30px;
            align-items: center;
        }

        nav a {
            color: #333;
            text-decoration: none;
            font-weight: 600;
            font-size: 16px;
            padding: 10px 20px;
            border-radius: 5px;
            background: linear-gradient(to bottom, #fff 0%, #f9f9f9 100%);
            border: 1px solid #ddd;
        }

        nav a.login-btn {
            margin-left: 30px;
            background: linear-gradient(to bottom, #333 0%, #222 100%);
            color: white;
            border-color: #333;
        }

        /* Hero Section */
        .hero {
            position: relative;
            width: 100%;
            height: 500px;
            overflow: hidden;
            border-bottom: 5px solid #ff8c00;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .hero img {
            width: 100%;
            height: 100%;
            object-fit: cover;
            object-position: 60% center;
        }

        .hero-overlay {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.4);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 30px;
        }

        .hero-overlay h2 {
            font-size: 48px;
            color: white;
            text-shadow: 2px 2px 8px rgba(0,0,0,0.8);
            text-align: center;
        }

        .hero-cta {
            display: inline-block;
            background: rgba(255,140,0,0.9);
            color: white;
            padding: 20px 50px;
            border-radius: 5px;
            text-decoration: none;
            font-weight: bold;
            font-size: 24px;
        }

        /* Main Content */
        main {
            background: white;
            margin: 30px auto;
            max-width: 1200px;
            padding: 40px;
            border-radius: 8px;
        }

        /* Offset Image Sections */
        .service-section {
            display: flex;
            align-items: center;
            gap: 40px;
            margin: 60px 0;
            padding: 30px;
            background: linear-gradient(to right, #f9f9f9 0%, white 100%);
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }

        .service-section:nth-child(even) {
            flex-direction: row-reverse;
            background: linear-gradient(to left, #f9f9f9 0%, white 100%);
        }

        .service-image {
            flex: 0 0 300px;
            position: relative;
        }

        .service-image img {
            width: 100%;
            height: auto;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            border: 5px solid white;
        }

        .service-content {
            flex: 1;
        }

        .service-content h3 {
            color: #ff8c00;
            font-size: 28px;
            margin-bottom: 15px;
        }

        .service-content p {
            font-size: 16px;
            line-height: 1.8;
            color: #555;
        }

        /* Call to Action */
        .cta-section {
            background: linear-gradient(135deg, #ff8c00 0%, #ff7700 100%);
            color: white;
            padding: 40px;
            border-radius: 8px;
            text-align: center;
            margin: 40px 0;
        }

        .cta-section h3 {
            font-size: 32px;
            margin-bottom: 15px;
        }

        .cta-section p {
            font-size: 18px;
            margin-bottom: 20px;
        }

        .cta-button {
            display: inline-block;
            background: white;
            color: #ff8c00;
            padding: 15px 40px;
            border-radius: 5px;
            text-decoration: none;
            font-weight: bold;
            font-size: 18px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            transition: all 0.3s ease;
        }

        .cta-button:hover {
            transform: translateY(-3px);
            box-shadow: 0 6px 12px rgba(0,0,0,0.3);
            background: #333;
            color: white;
        }

        /* Footer */
        footer {
            background: linear-gradient(to bottom, #333 0%, #222 100%);
            color: white;
            text-align: center;
            padding: 30px;
            margin-top: 40px;
            box-shadow: 0 -2px 8px rgba(0,0,0,0.2);
        }

        /* Full Page Background */
        #fullPageMan {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            object-fit: cover;
            object-position: right center;
            z-index: -1;
            opacity: 0;
            transition: opacity 0.3s ease;
        }
    </style>
    <script>
        let scrollVelocity = 0;
        let isScrolling = false;

        // :-)
        window.addEventListener('wheel', function(e) {
            e.preventDefault();

            const delta = e.deltaY;
            scrollVelocity += delta * 0.05;

            if (!isScrolling) {
                isScrolling = true;
                smoothScroll();
            }
        }, { passive: false });

        function smoothScroll() {
            if (Math.abs(scrollVelocity) > 0.05) {
                window.scrollBy(0, scrollVelocity);
                scrollVelocity *= 0.95;
                requestAnimationFrame(smoothScroll);
            } else {
                scrollVelocity = 0;
                isScrolling = false;
            }
        }
    </script>
</head>
<body>
    <header>
        <div class="container">
            <h1><img src="images/logo.png" alt="Tangerine Printing Logo" height="50"> Tangerine Printing</h1>
            <nav>
                <a href="index.php">Home</a>
                <a href="team.php">Who We Are</a>
                <a href="contact.php">Submit Design</a>
                <a href="https://auth.tangerineprinting.biz" class="login-btn">Employee Login</a>
            </nav>
        </div>
    </header>
