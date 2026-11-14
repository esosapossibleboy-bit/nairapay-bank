CARD_AND_RENDER_JS = """
    async function issueCard() {
        cardMsg.textContent = "";
        const res = await fetch("/wallet/cards", { method:"POST", headers:headers(), body:JSON.stringify({ currency:newCardCurrency.value }) });
        if (res.ok) renderWallet(await res.json());
    }
    async function fundCard(id) {
        const amt = prompt("Enter Naira (₦) amount to fund this card (1 USD = ₦1,600):");
        if (!amt) return;
        cardMsg.className = "error"; cardMsg.textContent = "";
        const res = await fetch(`/wallet/cards/${id}/fund`, { method:"POST", headers:headers(), body:JSON.stringify({ amount:parseFloat(amt), timestamp:getLocalTime() }) });
        const data = await res.json();
        if (!res.ok) return cardMsg.textContent = data.detail || "Funding failed";
        cardMsg.className = "success"; cardMsg.textContent = `✅ Card Funded (${data.reference})`;
        renderWallet(data.dashboard);
    }
    async function freezeCard(id) {
        const res = await fetch(`/wallet/cards/${id}/freeze`, { method:"POST", headers:headers() });
        if (res.ok) renderWallet(await res.json());
    }
    async function revealCard(id) {
        const pin = prompt("Enter your 4-digit Transaction PIN to view full card number & CVV:");
        if (!pin) return;
        const res = await fetch(`/wallet/cards/${id}/reveal`, { method:"POST", headers:headers(), body:JSON.stringify({ pin }) });
        const data = await res.json();
        if (!res.ok) return alert(data.detail || "Invalid PIN");
        alert(`Card Number: ${data.card_number}\\nExpiry: ${data.expiry}\\nCVV: ${data.cvv}`);
    }
    async function updatePin() {
        pinResetMsg.className = "error"; pinResetMsg.textContent = "";
        const res = await fetch("/auth/change-pin", {
            method: "POST",
            headers: headers(),
            body: JSON.stringify({ password: pinResetPass.value, new_pin: pinResetNew.value })
        });
        const data = await res.json();
        if (!res.ok) return pinResetMsg.textContent = Array.isArray(data.detail) ? data.detail.map(x => x.msg).join(", ") : (data.detail || "PIN update failed");
        pinResetMsg.className = "success";
        pinResetMsg.textContent = "✅ 4-Digit Transaction PIN Updated Successfully!";
        pinResetPass.value = pinResetNew.value = "";
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
        vaultBalText.textContent = "₦" + (d.vault_naira || 0).toLocaleString("en-NG", { minimumFractionDigits:2, maximumFractionDigits:2 });
        beneficiaryBar.replaceChildren(...(d.beneficiaries || []).map(b =>
            Object.assign(document.createElement("button"), {
                type: "button", className: "btn-secondary",
                style: "width:auto;margin:0;padding:6px 10px;font-size:0.85rem;",
                textContent: `👤 ${b.name}`, onclick: () => selectBeneficiary(b.account_number)
            })
        ));
        cardsGrid.replaceChildren(...(d.cards || []).map(c => {
            const box = Object.assign(document.createElement("div"), { style:"background:#0b131e;border:1px solid #2b3f5c;border-radius:12px;padding:14px;" });
            const sym = c.currency === "NGN" ? "₦" : "$";
            box.append(
                Object.assign(document.createElement("div"), { textContent:`${c.brand} ${c.is_frozen ? "❄️ (FROZEN)" : "✅"}`, style:"font-weight:700;color:#00d285;" }),
                Object.assign(document.createElement("div"), { textContent:`${c.masked_number} • Exp ${c.expiry}`, style:"margin:6px 0;font-family:monospace;" }),
                Object.assign(document.createElement("div"), { textContent:`Card Balance: ${sym}${c.balance.toFixed(2)}`, style:"margin-bottom:8px;" }),
                Object.assign(document.createElement("button"), { style:"padding:8px;margin-top:4px;", textContent:"+ Fund Card (₦)", onclick:()=>fundCard(c.id) }),
                Object.assign(document.createElement("button"), { className:"btn-secondary", style:"padding:8px;margin-top:6px;", textContent:"👁️ Reveal Number & CVV", onclick:()=>revealCard(c.id) }),
                Object.assign(document.createElement("button"), { className:"btn-secondary", style:"padding:8px;margin-top:6px;", textContent:c.is_frozen ? "🔥 Unfreeze Card" : "❄️ Freeze Card", onclick:()=>freezeCard(c.id) })
            );
            return box;
        }));
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
"""
