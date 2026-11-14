from opay_card_js import CARD_AND_RENDER_JS

CORE_BANK_JS = """
    let token = localStorage.getItem("opay_token") || "", idleTimer = null, isRegisterMode = false;
    const IDLE_MS = 10 * 60 * 1000;
    const headers = () => ({ "Content-Type": "application/json", "Authorization": "Bearer " + token });
    function getLocalTime() {
        const d = new Date(), tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "Africa/Lagos";
        return d.toLocaleString("en-GB", { day:"2-digit", month:"short", year:"numeric", hour:"2-digit", minute:"2-digit" }) + ` (${tz})`;
    }
    function makeIdemKey() {
        return (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : ("idem-" + Date.now() + "-" + Math.random().toString(36).slice(2));
    }
    function resetIdle() {
        if (!token) return;
        localStorage.setItem("opay_last", String(Date.now()));
        clearTimeout(idleTimer);
        idleTimer = setTimeout(() => logout("🔒 Auto-locked after 10 minutes of inactivity."), IDLE_MS);
    }
    ["click", "touchstart", "keydown", "scroll"].forEach(e => window.addEventListener(e, resetIdle, { passive: true }));
    function toggleAuthMode() {
        isRegisterMode = !isRegisterMode;
        authError.textContent = "";
        nameInput.value = emailInput.value = passInput.value = pinInput.value = "";
        registerFields.style.display = isRegisterMode ? "block" : "none";
        registerPinBox.style.display = isRegisterMode ? "block" : "none";
        authTitle.textContent = isRegisterMode ? "🏦 Create Free Bank Account" : "🔐 Log In to NairaPay";
        passInput.placeholder = isRegisterMode ? "Create Strong Password (8+ chars, A-z, 0-9, !@#)" : "Password";
        primaryAuthBtn.textContent = isRegisterMode ? "Create Free Bank Account" : "Log In";
        toggleAuthBtn.textContent = isRegisterMode ? "Already have an account? Log In" : "New user? Create Free Account";
    }
    async function submitAuth() {
        authError.textContent = "";
        const url = isRegisterMode ? "/auth/register" : "/auth/login";
        const payload = isRegisterMode
            ? { full_name:nameInput.value.trim(), email:emailInput.value.trim(), password:passInput.value, pin:pinInput.value }
            : { email:emailInput.value.trim(), password:passInput.value };
        const res = await fetch(url, { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload) });
        const data = await res.json();
        if (!res.ok) return authError.textContent = Array.isArray(data.detail) ? data.detail.map(x => x.msg).join(", ") : (data.detail || "Auth error");
        token = data.token; localStorage.setItem("opay_token", token);
        nameInput.value = emailInput.value = passInput.value = pinInput.value = "";
        authCard.style.display = "none"; bankArea.style.display = "block";
        resetIdle(); loadWallet();
    }
    async function logout(msg = "") {
        clearTimeout(idleTimer);
        if (token) await fetch("/auth/logout", { method:"POST", headers:headers() }).catch(() => {});
        token = ""; localStorage.clear();
        nameInput.value = emailInput.value = passInput.value = pinInput.value = "";
        bankArea.style.display = "none"; authCard.style.display = "block";
        authError.textContent = typeof msg === "string" ? msg : "";
    }
    async function loadWallet() {
        const res = await fetch("/wallet", { headers:headers() });
        if (res.status === 401) return logout("Session expired.");
        renderWallet(await res.json());
    }
    async function checkRecipient() {
        recipNamePreview.textContent = "";
        if (recipAcct.value.trim().length !== 10) return;
        const res = await fetch(`/wallet/lookup/${recipAcct.value.trim()}`, { headers:headers() });
        if (res.ok) { const d = await res.json(); recipNamePreview.textContent = "✅ Verified Recipient: " + d.full_name; }
        else recipNamePreview.textContent = "❌ Account number not found";
    }
    function selectBeneficiary(acct) { recipAcct.value = acct; checkRecipient(); }
    async function topUpWallet() {
        billMsg.className = "error"; billMsg.textContent = "";
        const res = await fetch("/wallet/deposit", { method:"POST", headers:headers(), body:JSON.stringify({ amount:parseFloat(topupAmount.value), pin:topupPin.value, timestamp:getLocalTime() }) });
        const data = await res.json();
        if (!res.ok) return billMsg.textContent = data.detail || "Top-up failed";
        billMsg.className = "success"; billMsg.textContent = "✅ Wallet Top-Up Successful";
        topupAmount.value = topupPin.value = ""; renderWallet(data);
    }
    async function sendMoney() {
        sendMsg.className = "error"; sendMsg.textContent = "";
        const res = await fetch("/wallet/transfer", { method:"POST", headers:headers(), body:JSON.stringify({ recipient_account:recipAcct.value.trim(), amount:parseFloat(sendAmount.value), pin:sendPin.value, narration:sendNote.value, timestamp:getLocalTime(), idempotency_key:makeIdemKey() }) });
        const data = await res.json();
        if (!res.ok) return sendMsg.textContent = data.detail || "Transfer failed";
        sendMsg.className = "success"; sendMsg.textContent = `✅ Sent ₦${Number(sendAmount.value).toLocaleString()} (${data.reference})`;
        recipAcct.value = sendAmount.value = sendNote.value = sendPin.value = recipNamePreview.textContent = "";
        renderWallet(data.dashboard);
    }
    async function payUtilityBill() {
        billMsg.className = "error"; billMsg.textContent = "";
        const res = await fetch("/wallet/bills", { method:"POST", headers:headers(), body:JSON.stringify({ service:billService.value, target:billTarget.value, amount:parseFloat(billAmount.value), pin:billPin.value, timestamp:getLocalTime() }) });
        const data = await res.json();
        if (!res.ok) return billMsg.textContent = data.detail || "Bill payment failed";
        billMsg.className = "success"; billMsg.textContent = `✅ Paid (${data.reference})`;
        billTarget.value = billAmount.value = billPin.value = "";
        renderWallet(data.dashboard);
    }
    async function saveToVault() {
        vaultMsg.className = "error"; vaultMsg.textContent = "";
        const res = await fetch("/wallet/vault/save", { method:"POST", headers:headers(), body:JSON.stringify({ amount:parseFloat(vaultSaveAmt.value), pin:vaultSavePin.value, timestamp:getLocalTime() }) });
        const data = await res.json();
        if (!res.ok) return vaultMsg.textContent = data.detail || "Save failed";
        vaultMsg.className = "success"; vaultMsg.textContent = `✅ Saved (${data.reference})`;
        vaultSaveAmt.value = vaultSavePin.value = ""; renderWallet(data.dashboard);
    }
    async function earnInterest() {
        const pin = prompt("Enter your 4-digit Transaction PIN to simulate 30-day 15% interest:");
        if (!pin) return;
        vaultMsg.className = "error"; vaultMsg.textContent = "";
        const res = await fetch("/wallet/vault/interest", { method:"POST", headers:headers(), body:JSON.stringify({ pin }) });
        const data = await res.json();
        if (!res.ok) return vaultMsg.textContent = data.detail || "Interest error";
        vaultMsg.className = "success"; vaultMsg.textContent = `🌟 30-Day 15% Interest Credited (${data.reference})`;
        renderWallet(data.dashboard);
    }
    async function withdrawVault() {
        vaultMsg.className = "error"; vaultMsg.textContent = "";
        const res = await fetch("/wallet/vault/withdraw", { method:"POST", headers:headers(), body:JSON.stringify({ amount:parseFloat(vaultWdrAmt.value), pin:vaultPin.value, timestamp:getLocalTime() }) });
        const data = await res.json();
        if (!res.ok) return vaultMsg.textContent = data.detail || "Withdrawal failed";
        vaultMsg.className = "success"; vaultMsg.textContent = `✅ Withdrawn to Wallet (${data.reference})`;
        vaultWdrAmt.value = vaultPin.value = ""; renderWallet(data.dashboard);
    }
"""

OPAY_JS = f"<script>\n{CORE_BANK_JS}\n{CARD_AND_RENDER_JS}\n</script>"
