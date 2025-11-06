document.addEventListener('DOMContentLoaded', () => {
    
    console.log("✅ DOM Content Loaded: Script is running.");

    const API_ENDPOINT = 'YOUR_CDK_API_ENDPOINT_OUTPUT';
    console.log(`API Endpoint set to: ${API_ENDPOINT}`);


    // --- 2. Get all the HTML elements we need ---
    const form = document.getElementById('tracker-form');
    const trackBtn = document.getElementById('track-btn');
    const statusMsg = document.getElementById('status-message');

    // --- Elements for Service Type (Price/Stock) ---
    const serviceTypeDropdown = document.getElementById('service-type');
    const priceInputWrapper = document.getElementById('price-input-wrapper');
    const targetPriceInput = document.getElementById('target-price');

    // --- Elements for Notification Type (Email/Telegram) ---
    const notificationType = document.getElementById('notification-type');
    const targetLabel = document.getElementById('target-label');
    const targetInput = document.getElementById('notification-target');
    const targetHelpText = document.getElementById('target-help-text');
    
    console.log("All form elements captured.");

    
    // --- 3. Add listener for the Service Type dropdown ---
    serviceTypeDropdown.addEventListener('change', () => {
        const selectedService = serviceTypeDropdown.value;
        console.log(`🔧 Service type changed to: ${selectedService}`);

        if (selectedService === 'STOCK') {
            priceInputWrapper.classList.add('hidden');
            targetPriceInput.required = false;
        } else {
            priceInputWrapper.classList.remove('hidden');
            targetPriceInput.required = true;
        }
    });

    
    // --- 4. Add listener for the Notification dropdown (THIS IS THE FIX) ---
    notificationType.addEventListener('change', () => {
        const selectedType = notificationType.value;
        console.log(`🔔 Notification type changed to: ${selectedType}`);

        if (selectedType === 'EMAIL') {
            targetLabel.innerText = 'Your Email';
            targetInput.type = 'email';
            targetInput.placeholder = 'you@example.com';
            targetHelpText.innerText = 'We\'ll send a confirmation here.';
        } else if (selectedType === 'TELEGRAM') {
            targetLabel.innerText = 'Your Telegram Chat ID';
            targetInput.type = 'text';
            targetInput.placeholder = '123456789';
            targetHelpText.innerText = 'Find this by messaging @userinfobot on Telegram.';
        }
    });


    // --- 5. Add listener for the form "submit" event ---
    form.addEventListener('submit', async (event) => {
        event.preventDefault(); 
        console.log("🚀 Form submitted.");

        // ... (UI set to 'loading' state logic) ...
        trackBtn.disabled = true;
        trackBtn.innerText = 'Tracking...';
        statusMsg.className = 'loading';
        statusMsg.innerText = 'Please wait... adding product to tracker.';

        // --- Get the values from the form ---
        const productUrl = document.getElementById('product-url').value;
        const targetPrice = targetPriceInput.value;
        const serviceType = serviceTypeDropdown.value;
        const notifType = notificationType.value;
        const notifTarget = targetInput.value;

        // --- Prepare the data for our Lambda function ---
        const payload = {
            url: productUrl,
            price: targetPrice || "0", // Send "0" if price is hidden
            serviceType: serviceType,
            notificationType: notifType,
            notificationTarget: notifTarget,
        };
        
        console.log("📦 Payload created:", JSON.stringify(payload, null, 2));

        try {
            console.log("📤 Sending data to API Gateway...");
            
            const response = await fetch(API_ENDPOINT, {
                method: 'POST',
                body: JSON.stringify(payload)
            });
            
            console.log("📬 Raw response received from API:", response);

            const responseBody = await response.json();
            console.log("📄 Parsed response body:", responseBody);

            if (!response.ok) {
                console.error(`Response not OK (${response.status}). Throwing error.`);
                throw new Error(responseBody.message || `HTTP Error: ${response.status}`);
            }

            // --- Handle Success ---
            console.log("✅ API call successful!");
            statusMsg.className = 'success';
            statusMsg.innerText = responseBody; 
            form.reset(); 
            
            // Manually trigger 'change' events to reset the fields to default
            serviceTypeDropdown.dispatchEvent(new Event('change'));
            notificationType.dispatchEvent(new Event('change'));

            console.log("Form reset.");

        } catch (error) {
            console.error("❌ Submission failed:", error);
            statusMsg.className = 'error';
            statusMsg.innerText = `Error: ${error.message}. Please try again.`;

        } finally {
            trackBtn.disabled = false;
            trackBtn.innerText = 'Track Product';
            console.log("UI state reset.");
        }
    });
});