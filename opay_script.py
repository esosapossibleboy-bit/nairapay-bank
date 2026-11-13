OPAY_JS = """
<script>
    let token = localStorage.getItem("opay_token") || "", idleTimer = null;
    const IDLE_MS = 10 * 60 * 1000;
    const headers = () => ({ "Content-Type": "application/json", "Authorization": "Bearer " + token });
    function getLocalTime() {
        const d = new Date(), tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "Africa/Lagos";
        return d.toLocaleString("en-GB", { day:"2-digit", month:"short", year:"numeric", hour:"2-digit", minute:"2-digit" }) + ` (${tz})`;
    }
    function resetIdle() {
        if (!token) return;
        localStorage.setItem("opay_last", String(Date.now()));
        clearTimeout(idleTimer);
        idleTimer = setTimeout(() => logout("🔒 Auto-locked after 10 minutes of inactivity."), IDLE_MS);
    }
    ["click", "touchstart", "keydown", "scroll"].forEach(e => window.addEventListener(e, resetIdle, { passive: true }));
    async function submitAuth(url) {
        authError.textContent = "";
        const res = await fetch(url, { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ full_name:nameInput.value.trim()||"Customer", email:emailInput.value.trim(), password:passInput.value, pin:pinInput.value }) });
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
    async function topUpWallet() {
        billMsg.textContent = "";
        const res = await fetch("/wallet/deposit", { method:"POST", headers:headers(), body:JSON.stringify({ amount:parseFloat(topupAmount.value), timestamp:getLocalTime() }) });
        if (res.ok) { topupAmount.value = ""; renderWallet(await res.json()); }
    }
    async function sendMoney() {
        sendMsg.className = "error"; sendMsg.textContent = "";
        const res = await fetch("/wallet/transfer", { method:"POST", headers:headers(), body:JSON.stringify({ recipient_account:recipAcct.value.trim(), amount:parseFloat(sendAmount.value), pin:sendPin.value, narration:sendNote.value, timestamp:getLocalTime() }) });
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
    async function downloadStatement() {
        const res = await fetch("/wallet/statement/pdf", { headers:headers() });
        if (!res.ok) return;
        const blob = await res.blob(), url = URL.createObjectURL(blob);
        const a = Object.assign(document.createElement("a"), { href:url, download:"nairapay_statement.pdf" });
        document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
    }
    function renderWallet(d) {
        holderName.textContent = "👋 " + d.full_name;
        acctNumText.textContent = d.account_number;
        balanceText.textContent = "₦" + d.balance_naira.toLocaleString("en-NG", { minimumFractionDigits:2, maximumFractionDigits:2 });
        txList.replaceChildren(...d.transactions.map(tx => {
            const row = Object.assign(document.createElement("div"), { className:"tx-row" });
            const left = document.createElement("div");
            left.append(
                Object.assign(document.createElement("div"), { textContent:`${tx.counterparty} — ${tx.narration}` }),
                Object.assign(document.createElement("small"), { textContent:`${tx.reference} • ${tx.created_at}`, style:"color:#94a3b8;" })
            );
            const amt = Object.assign(document.createElement("span"), {
                className: tx.type === "CREDIT" ? "credit" : "debit",
                textContent: `${tx.type === "CREDIT" ? "+" : "-"}₦${tx.amount_naira.toLocaleString("en-NG", { minimumFractionDigits:2 })}`
            });
            row.append(left, amt); return row;
        }));
    }
    if (token) { authCard.style.display = "none"; bankArea.style.display = "block"; resetIdle(); loadWallet(); }
</script>
"""
