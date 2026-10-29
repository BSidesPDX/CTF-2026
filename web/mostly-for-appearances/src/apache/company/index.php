<?php $page_title = 'Tangerine Printing - Premium Screen Printing Services'; ?>
<?php include 'header.php'; ?>

<!-- Full Page Background Man -->
<img src="images/stock/man_happy_customer.png" alt="Background" id="fullPageMan">

<!-- Hero Section -->
<div class="hero">
    <img src="images/stock/man_happy_customer.png" alt="Happy Customer" id="heroImage">
    <div class="hero-overlay">
        <h2>The People Person's Printing People</h2>
        <a href="contact.php" class="hero-cta">Submit Your Design</a>
    </div>
</div>

<script>
    window.addEventListener('scroll', function() {
        const fullPageMan = document.getElementById('fullPageMan');
        const mainElement = document.querySelector('main');
        const scrollPosition = window.pageYOffset;
        const documentHeight = document.documentElement.scrollHeight - window.innerHeight;
        const scrollPercent = scrollPosition / documentHeight;

        // Show full page man and make main transparent when at bottom
        if (scrollPercent >= 0.95) {
            const fadeAmount = (scrollPercent - 0.95) / 0.05;
            fullPageMan.style.opacity = fadeAmount;
            mainElement.style.opacity = 1 - (fadeAmount * 0.5);
        } else {
            fullPageMan.style.opacity = 0;
            mainElement.style.opacity = 1;
        }
    });
</script>

<main>
    <h2 style="text-align: center; color: #ff8c00; font-size: 36px; margin-bottom: 20px;">Welcome to Tangerine Printing</h2>
    <p style="text-align: center; font-size: 18px; margin-bottom: 50px; color: #555;">Your premier destination for high-quality screen printing services.</p>

    <!-- Offset Service Sections -->
    <div class="service-section">
        <div class="service-image">
            <img src="images/irasutoya/fashion_class_tshirt_a.png" alt="Custom T-Shirt Printing">
        </div>
        <div class="service-content">
            <h3>Custom T-Shirt Printing</h3>
            <p>We will put your design on only the finest quality Gildan fabrics.</p>
        </div>
    </div>

    <div class="service-section">
        <div class="service-image">
            <img src="images/irasutoya/delivery_woman.png" alt="Fast Delivery">
        </div>
        <div class="service-content">
            <h3>Fast & Reliable Delivery</h3>
            <p>USPS, UPS, DHL only. We do <b>not</b> use FedEx after an unfortunate “you too” incident.</p>
        </div>
    </div>

    <div class="service-section">
        <div class="service-image">
            <img src="images/irasutoya/phone_woman4_laugh.png" alt="Customer Service">
        </div>
        <div class="service-content">
            <h3>Exceptional Customer Service</h3>
            <p>Alice is a wiz on the phones!</p>
        </div>
    </div>

    <div class="service-section">
        <div class="service-image">
            <img src="images/irasutoya/poster_putting_up.png" alt="Poster Printing">
        </div>
        <div class="service-content">
            <h3>Poster & Art Prints</h3>
            <p>Make a statement with our premium inks and papers!</p>
        </div>
    </div>

    <div class="service-section">
        <div class="service-image">
            <img src="images/irasutoya/job_designer.png" alt="Design Services">
        </div>
        <div class="service-content">
            <h3>Professional Design Services</h3>
            <p>We own <b>fully legal</b> copies of Adobe Photoshop CS6! If you tell us you made your design in Canva, we may ask you to leave.</p>
        </div>
    </div>

    <div class="service-section">
        <div class="service-image">
            <img src="images/irasutoya/printer_print_color_bad.png" alt="High Quality Photo Printing">
        </div>
        <div class="service-content">
            <h3>High Quality Photo Printing</h3>
            <p>Great photos deserve great prints! Shown: Another satisfied customer.</p>
        </div>
    </div>

    <!-- Call to Action -->
    <div class="cta-section">
        <h3>Ready to Get Started?</h3>
        <p>Have a design ready? We'll get back to you with a quote within 24 hours!</p>
        <a href="contact.php" class="cta-button">Submit Your Design</a>
    </div>

    <div style="text-align: center; margin-top: 40px;">
        <p style="font-size: 16px; color: #555;">Want to learn more about our team? <a href="team.php" style="color: #ff8c00; font-weight: bold;">Meet the talented “people”</a> behind Tangerine Printing.</p>
    </div>
</main>

<?php include 'footer.php'; ?>
