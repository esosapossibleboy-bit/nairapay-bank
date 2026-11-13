from fpdf import FPDF, XPos, YPos

def clean_latin1(text: str) -> str:
    return str(text).encode("latin-1", "replace").decode("latin-1")

def build_bank_statement_pdf(dashboard: dict) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "NairaPay Microfinance Bank - Account Statement", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, clean_latin1(f"Account Name: {dashboard['full_name']}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 8, clean_latin1(f"Account Number: {dashboard['account_number']}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 8, clean_latin1(f"Available Balance: NGN {dashboard['balance_naira']:,.2f}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Transaction Ledger:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9)

    if not dashboard["transactions"]:
        pdf.cell(0, 8, "No transactions recorded yet.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    else:
        for tx in dashboard["transactions"]:
            sign = "+" if tx["type"] == "CREDIT" else "-"
            line = f"[{tx['created_at']}] {tx['reference']} | {tx['counterparty']} ({tx['narration']}) : {sign}NGN {tx['amount_naira']:,.2f}"
            pdf.cell(0, 7, clean_latin1(line), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    raw_out = pdf.output()
    return raw_out.encode("latin-1") if isinstance(raw_out, str) else bytes(raw_out)
