/**
 * WhatsApp approval + feedback script.
 *
 * Usage: node send_and_wait.js --phone 972XXXXXXXXX --message "Post preview text"
 *
 * Flow:
 * 1. Initialize whatsapp-web.js (uses saved auth session)
 * 2. First run: shows QR code for scanning
 * 3. Sends message to the specified phone number
 * 4. Waits for reply:
 *    - "אישור" / "approve" → prints "APPROVED" to stdout
 *    - "ביטול" / "cancel"  → prints "REJECTED" to stdout
 *    - Any other text       → prints "FEEDBACK: <text>" to stdout (user wants changes)
 * 5. Exits after receiving a reply or timeout
 */

const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const path = require('path');

// Parse command line arguments
const args = {};
for (let i = 2; i < process.argv.length; i += 2) {
    const key = process.argv[i].replace('--', '');
    args[key] = process.argv[i + 1];
}

const phone = args.phone;
const message = args.message;
const timeout = parseInt(args.timeout || '1800') * 1000; // default 30 min

if (!phone || !message) {
    console.error('Usage: node send_and_wait.js --phone 972XXXXXXXXX --message "text" [--timeout 1800]');
    process.exit(1);
}

const chatId = phone.includes('@c.us') ? phone : `${phone}@c.us`;

const client = new Client({
    authStrategy: new LocalAuth({
        dataPath: path.join(__dirname, '.wwebjs_auth'),
    }),
    puppeteer: {
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
    },
});

let messageSent = false;
let timeoutHandle;

client.on('qr', (qr) => {
    console.error('[WhatsApp] Scan QR code to authenticate:');
    qrcode.generate(qr, { small: true });
});

client.on('authenticated', () => {
    console.error('[WhatsApp] Authenticated successfully');
});

client.on('ready', async () => {
    console.error('[WhatsApp] Client ready');

    try {
        const fullMessage = `${message}\n\n---\nהשב *אישור* כדי לפרסם\nהשב *ביטול* כדי לבטל\nאו שלח הערות לתיקון`;
        await client.sendMessage(chatId, fullMessage);
        messageSent = true;
        console.error('[WhatsApp] Message sent, waiting for reply...');

        // Set timeout
        timeoutHandle = setTimeout(() => {
            console.log('TIMEOUT');
            cleanup();
        }, timeout);
    } catch (err) {
        console.error(`[WhatsApp] Error sending message: ${err.message}`);
        console.log('ERROR');
        cleanup();
    }
});

client.on('message', async (msg) => {
    if (!messageSent) return;

    // Only listen for messages from the target phone
    const fromId = msg.from;
    if (fromId !== chatId) return;

    const body = msg.body.trim();
    clearTimeout(timeoutHandle);

    if (body === 'אישור' || body.toLowerCase() === 'approve') {
        console.log('APPROVED');
        await client.sendMessage(chatId, '✅ הפוסט אושר ומתפרסם כעת...');
        cleanup();
    } else if (body === 'ביטול' || body.toLowerCase() === 'cancel') {
        console.log('REJECTED');
        await client.sendMessage(chatId, '❌ הפרסום בוטל.');
        cleanup();
    } else {
        // User sent feedback for fixes
        console.log(`FEEDBACK: ${body}`);
        await client.sendMessage(chatId, '📝 קיבלתי את ההערות, מתקן ושולח שוב...');
        cleanup();
    }
});

client.on('auth_failure', () => {
    console.error('[WhatsApp] Authentication failed');
    console.log('ERROR');
    process.exit(1);
});

function cleanup() {
    setTimeout(async () => {
        try {
            await client.destroy();
        } catch (e) {
            // ignore
        }
        process.exit(0);
    }, 2000);
}

// Start the client
client.initialize();
