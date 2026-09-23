import csv
import tkinter as tk
from xml.sax.saxutils import escape
from datetime import date, timedelta
from tkinter import ttk,filedialog,messagebox
from database import connect
from services.money import fmt

class JournalFrame(ttk.Frame):
    def __init__(self,master):
        super().__init__(master,padding=10)
        top=ttk.Frame(self);top.pack(fill="x")
        ttk.Label(top,text="Journal / التقارير",font=("Segoe UI",22,"bold")).pack(side="left")
        ttk.Button(top,text="Export CSV",command=self.export).pack(side="right");ttk.Button(top,text="Export Excel",command=self.export_excel).pack(side="right",padx=5);ttk.Button(top,text="Export PDF",command=self.export_pdf).pack(side="right",padx=5);ttk.Button(top,text="Rapport articles",command=self.article_report).pack(side="right",padx=5);ttk.Button(top,text="Rapport familles",command=self.family_report).pack(side="right",padx=5);ttk.Button(top,text="Rapport clients",command=self.client_report).pack(side="right",padx=5);ttk.Button(top,text="Rapport jours",command=self.day_report).pack(side="right",padx=5);ttk.Button(top,text="Actualiser",command=self.refresh).pack(side="right",padx=5)
        filters=ttk.Frame(self);filters.pack(fill="x",pady=8)
        today=date.today();self.date_from=tk.StringVar(value=str(today));self.date_to=tk.StringVar(value=str(today));self.cashier=tk.StringVar(value="Tous");self.payment=tk.StringVar(value="Tous")
        for label,var,width in [("Du",self.date_from,11),("Au",self.date_to,11)]:ttk.Label(filters,text=label).pack(side="left");ttk.Entry(filters,textvariable=var,width=width).pack(side="left",padx=(3,10))
        ttk.Label(filters,text="Caissier").pack(side="left");self.cashier_box=ttk.Combobox(filters,textvariable=self.cashier,state="readonly",width=16);self.cashier_box.pack(side="left",padx=(3,10))
        ttk.Label(filters,text="Paiement").pack(side="left");ttk.Combobox(filters,textvariable=self.payment,values=["Tous","CASH","CARD","MIXED","CREDIT"],state="readonly",width=10).pack(side="left",padx=(3,10))
        ttk.Button(filters,text="Aujourd’hui",command=lambda:self.set_period(0)).pack(side="left",padx=2);ttk.Button(filters,text="7 jours",command=lambda:self.set_period(6)).pack(side="left",padx=2);ttk.Button(filters,text="30 jours",command=lambda:self.set_period(29)).pack(side="left",padx=2);ttk.Button(filters,text="Consulter",command=self.refresh).pack(side="right")
        cols=("id","ticket","date","cashier","pay","total","cost","margin")
        self.t=ttk.Treeview(self,columns=cols,show="headings")
        for c,h,w in [("id","ID",45),("ticket","Ticket",190),("date","Date",160),("cashier","Caissier",110),("pay","Paiement",90),("total","Total",90),("cost","Coût",90),("margin","Marge brute",100)]:self.t.heading(c,text=h);self.t.column(c,width=w,anchor="center")
        self.t.pack(fill="both",expand=True)
        self.summary=ttk.Label(self,text="",font=("Segoe UI",11,"bold"));self.summary.pack(anchor="e",pady=6)
        with connect() as c:names=[r[0] for r in c.execute("SELECT display_name FROM users WHERE active=1 ORDER BY display_name").fetchall()]
        self.cashier_box["values"]=["Tous",*names]
        self.refresh()
    def set_period(self,days):
        end=date.today();self.date_to.set(str(end));self.date_from.set(str(end-timedelta(days=days)));self.refresh()
    def rows(self):
        try:
            date.fromisoformat(self.date_from.get());date.fromisoformat(self.date_to.get())
        except ValueError:
            messagebox.showerror("Journal","Dates au format YYYY-MM-DD.",parent=self);return []
        where=["date(s.created_at)>=?","date(s.created_at)<=?"];params=[self.date_from.get(),self.date_to.get()]
        if self.cashier.get()!="Tous":where.append("u.display_name=?");params.append(self.cashier.get())
        if self.payment.get()!="Tous":
            if self.payment.get() in ("CASH","CARD"):
                where.append("EXISTS (SELECT 1 FROM sale_payments sp WHERE sp.sale_id=s.id AND sp.payment_method=?)");params.append(self.payment.get())
            else:
                where.append("s.payment_method=?");params.append(self.payment.get())
        sql="""SELECT s.id,s.sale_no,s.created_at,u.display_name,s.payment_method,
          COALESCE((SELECT SUM(sp.amount_cents) FROM sale_payments sp WHERE sp.sale_id=s.id AND sp.payment_method=\'CASH\'),0) cash_paid,
          COALESCE((SELECT SUM(sp.amount_cents) FROM sale_payments sp WHERE sp.sale_id=s.id AND sp.payment_method=\'CARD\'),0) card_paid,
          COALESCE((SELECT SUM(rp.amount_cents) FROM return_payments rp JOIN returns rr ON rr.id=rp.return_id WHERE rr.sale_id=s.id AND rp.payment_method=\'CASH\'),0) cash_refund,
          COALESCE((SELECT SUM(rp.amount_cents) FROM return_payments rp JOIN returns rr ON rr.id=rp.return_id WHERE rr.sale_id=s.id AND rp.payment_method=\'CARD\'),0) card_refund,
          s.total_cents-COALESCE((SELECT SUM(r.total_cents) FROM returns r WHERE r.sale_id=s.id),0) total_cents,
          COALESCE((SELECT SUM(si.cost_price_cents*si.qty) FROM sale_items si WHERE si.sale_id=s.id),0)
          -COALESCE((SELECT SUM(ri.qty*si.cost_price_cents) FROM return_items ri JOIN sale_items si ON si.id=ri.sale_item_id WHERE si.sale_id=s.id),0) cost
          FROM sales s JOIN users u ON u.id=s.cashier_user_id WHERE """+" AND ".join(where)+" ORDER BY s.id DESC LIMIT 5000"
        with connect() as c:return c.execute(sql,params).fetchall()
    def refresh(self):
        rows=self.rows();self.t.delete(*self.t.get_children());total=cost=0
        for r in rows:
            margin=int(r["total_cents"]-r["cost"]);total+=r["total_cents"];cost+=r["cost"]
            pay=r["payment_method"]
            if pay=="MIXED":pay="MIXED (Cash {} + Card {})".format(fmt(r["cash_paid"]-r["cash_refund"],""),fmt(r["card_paid"]-r["card_refund"],""))
            self.t.insert("", "end",values=(r["id"],r["sale_no"],r["created_at"],r["display_name"],pay,fmt(r["total_cents"],""),fmt(r["cost"],""),fmt(margin,"")))
        self.summary.config(text=f"{len(rows)} ticket(s) · Ventes nettes {fmt(total)} · Coût {fmt(cost)} · Marge brute {fmt(total-cost)}")
    def detail_report(self,mode):
        try:
            date.fromisoformat(self.date_from.get());date.fromisoformat(self.date_to.get())
        except ValueError:
            messagebox.showerror("Journal","Dates au format YYYY-MM-DD.",parent=self);return
        if mode=="article":
            group="p.id,p.name";label="Article";select="p.name"
        else:
            group="COALESCE(cat.id,0),COALESCE(cat.name,'Sans famille')";label="Famille";select="COALESCE(cat.name,'Sans famille')"
        sql=f"""SELECT {select} label,
            SUM(si.qty-COALESCE((SELECT SUM(ri.qty) FROM return_items ri WHERE ri.sale_item_id=si.id),0)) qty,
            SUM(si.line_total_cents-COALESCE((SELECT SUM(ri.total_cents) FROM return_items ri WHERE ri.sale_item_id=si.id),0)) gross,
            SUM(si.cost_price_cents*(si.qty-COALESCE((SELECT SUM(ri.qty) FROM return_items ri WHERE ri.sale_item_id=si.id),0))) cost
            FROM sale_items si JOIN sales s ON s.id=si.sale_id JOIN products p ON p.id=si.product_id
            LEFT JOIN categories cat ON cat.id=p.category_id
            WHERE date(s.created_at)>=? AND date(s.created_at)<=? GROUP BY {group} ORDER BY gross DESC"""
        with connect() as c:rows=c.execute(sql,(self.date_from.get(),self.date_to.get())).fetchall()
        w=tk.Toplevel(self);w.title(f"Rapport par {label}");w.geometry("850x560");w.transient(self.winfo_toplevel())
        tree=ttk.Treeview(w,columns=("label","qty","sales","cost","margin"),show="headings")
        for key,title,width in [("label",label,280),("qty","Qté",90),("sales","Ventes",120),("cost","Coût",120),("margin","Marge brute",120)]:tree.heading(key,text=title);tree.column(key,width=width,anchor="e" if key!="label" else "w")
        tree.pack(fill="both",expand=True,padx=12,pady=12)
        total=cost=0
        for r in rows:
            total+=r["gross"];cost+=r["cost"];tree.insert("","end",values=(r["label"],f"{r['qty']:g}",fmt(r["gross"],""),fmt(r["cost"],""),fmt(r["gross"]-r["cost"],"")))
        ttk.Label(w,text=f"Total {fmt(total)} · Coût {fmt(cost)} · Marge {fmt(total-cost)}",font=("Segoe UI",11,"bold")).pack(anchor="e",padx=12,pady=(0,12))
    def article_report(self):self.detail_report("article")
    def family_report(self):self.detail_report("family")
    def client_report(self):
        try:
            date.fromisoformat(self.date_from.get());date.fromisoformat(self.date_to.get())
        except ValueError:
            messagebox.showerror("Journal","Dates au format YYYY-MM-DD.",parent=self);return
        sql="""SELECT COALESCE(cl.name,'Client comptoir') label,COUNT(DISTINCT s.id) tickets,
            SUM(s.total_cents-COALESCE((SELECT SUM(r.total_cents) FROM returns r WHERE r.sale_id=s.id),0)) sales
            FROM sales s LEFT JOIN clients cl ON cl.id=s.client_id
            WHERE s.status='COMPLETED' AND date(s.created_at)>=? AND date(s.created_at)<=?
            GROUP BY s.client_id ORDER BY sales DESC"""
        with connect() as c:rows=c.execute(sql,(self.date_from.get(),self.date_to.get())).fetchall()
        w=tk.Toplevel(self);w.title("Rapport clients");w.geometry("700x540");w.transient(self.winfo_toplevel())
        tree=ttk.Treeview(w,columns=("client","tickets","sales"),show="headings")
        for key,title,width in [("client","Client",330),("tickets","Tickets",100),("sales","Ventes nettes",150)]:tree.heading(key,text=title);tree.column(key,width=width,anchor="e" if key!="client" else "w")
        tree.pack(fill="both",expand=True,padx=12,pady=12)
        total=0
        for r in rows:
            total+=r["sales"] or 0;tree.insert("","end",values=(r["label"],r["tickets"],fmt(r["sales"] or 0,"")))
        ttk.Label(w,text=f"Total ventes nettes {fmt(total)}",font=("Segoe UI",11,"bold")).pack(anchor="e",padx=12,pady=(0,12))
    def day_report(self):
        try:
            date.fromisoformat(self.date_from.get());date.fromisoformat(self.date_to.get())
        except ValueError:
            messagebox.showerror("Journal","Dates au format YYYY-MM-DD.",parent=self);return
        sql="""SELECT date(s.created_at,'localtime') day,COUNT(*) tickets,
            SUM(s.total_cents-COALESCE((SELECT SUM(r.total_cents) FROM returns r WHERE r.sale_id=s.id),0)) sales
            FROM sales s WHERE s.status='COMPLETED' AND date(s.created_at)>=? AND date(s.created_at)<=?
            GROUP BY day ORDER BY day"""
        with connect() as c:rows=c.execute(sql,(self.date_from.get(),self.date_to.get())).fetchall()
        w=tk.Toplevel(self);w.title("Rapport par jours");w.geometry("650x540");w.transient(self.winfo_toplevel())
        tree=ttk.Treeview(w,columns=("day","tickets","sales"),show="headings")
        for key,title,width in [("day","Jour",180),("tickets","Tickets",100),("sales","Ventes nettes",180)]:tree.heading(key,text=title);tree.column(key,width=width,anchor="center" if key!="sales" else "e")
        tree.pack(fill="both",expand=True,padx=12,pady=12)
        total=0
        for r in rows:
            total+=r["sales"] or 0;tree.insert("","end",values=(r["day"],r["tickets"],fmt(r["sales"] or 0,"")))
        ttk.Label(w,text=f"Total ventes nettes {fmt(total)}",font=("Segoe UI",11,"bold")).pack(anchor="e",padx=12,pady=(0,12))

    def export_excel(self):
        p=filedialog.asksaveasfilename(defaultextension=".xlsx",filetypes=[("Excel","*.xlsx")],title="Exporter journal Excel")
        if not p:return
        rows=self.rows()
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font,PatternFill,Alignment
            wb=Workbook();ws=wb.active;ws.title="Journal ventes"
            headers=["ID","Ticket","Date","Caissier","Paiement","Total","Coût","Marge brute"];ws.append(headers)
            for cell in ws[1]:cell.font=Font(bold=True,color="FFFFFF");cell.fill=PatternFill("solid",fgColor="2563EB");cell.alignment=Alignment(horizontal="center")
            total=cost=0
            for r in rows:
                total+=r["total_cents"];cost+=r["cost"];pay=r["payment_method"]
                if pay=="MIXED":pay="MIXED (Cash {} + Card {})".format(fmt(r["cash_paid"]-r["cash_refund"],""),fmt(r["card_paid"]-r["card_refund"],""))
                ws.append([r["id"],r["sale_no"],r["created_at"],r["display_name"],pay,r["total_cents"]/100,r["cost"]/100,(r["total_cents"]-r["cost"])/100])
            ws.append([]);ws.append(["","","","","TOTAL",total/100,cost/100,(total-cost)/100])
            for col,width in {"A":8,"B":22,"C":20,"D":18,"E":14,"F":14,"G":14,"H":16}.items():ws.column_dimensions[col].width=width
            for row in ws.iter_rows(min_row=2,min_col=6,max_col=8):
                for cell in row:cell.number_format='#,##0.00'
            ws.freeze_panes="A2";ws.auto_filter.ref=ws.dimensions;wb.save(p);messagebox.showinfo("ToDo","Excel exporté.",parent=self)
        except Exception as e:messagebox.showerror("ToDo",str(e),parent=self)
    def export_pdf(self):
        p=filedialog.asksaveasfilename(defaultextension=".pdf",filetypes=[("PDF","*.pdf")],title="Exporter journal PDF")
        if not p:return
        rows=self.rows()
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate,Table,TableStyle,Paragraph,Spacer
            styles=getSampleStyleSheet();doc=SimpleDocTemplate(p,pagesize=landscape(A4),rightMargin=24,leftMargin=24,topMargin=24,bottomMargin=24)
            data=[["Ticket","Date","Caissier","Paiement","Total","Coût","Marge"]];total=cost=0
            for r in rows:
                total+=r["total_cents"];cost+=r["cost"];pay=r["payment_method"]
                if pay=="MIXED":pay="MIXED (Cash {} + Card {})".format(fmt(r["cash_paid"]-r["cash_refund"],""),fmt(r["card_paid"]-r["card_refund"],""))
                data.append([r["sale_no"],r["created_at"],r["display_name"],pay,fmt(r["total_cents"],""),fmt(r["cost"],""),fmt(r["total_cents"]-r["cost"],"")])
            table=Table(data,repeatRows=1,colWidths=[120,120,95,70,75,75,75]);table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#2563EB")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("GRID",(0,0),(-1,-1),0.3,colors.grey),("FONTSIZE",(0,0),(-1,-1),8),("ALIGN",(4,1),(-1,-1),"RIGHT"),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
            title=Paragraph(f"Journal des ventes — {escape(self.date_from.get())} au {escape(self.date_to.get())}",styles["Title"])
            summary=Paragraph(f"{len(rows)} ticket(s) — Ventes nettes {fmt(total)} — Coût {fmt(cost)} — Marge brute {fmt(total-cost)}",styles["Heading3"])
            doc.build([title,Spacer(1,10),summary,Spacer(1,10),table]);messagebox.showinfo("ToDo","PDF exporté.",parent=self)
        except Exception as e:messagebox.showerror("ToDo",str(e),parent=self)
    def export(self):
        p=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")],title="Exporter journal")
        if not p:return
        rows=self.rows()
        with open(p,"w",newline="",encoding="utf-8-sig") as f:
            wr=csv.writer(f);wr.writerow(["ID","Ticket","Date","Caissier","Paiement","Total cents","Cost cents","Margin cents"])
            for r in rows:
                pay=r["payment_method"]
                if pay=="MIXED":pay="MIXED (Cash {} + Card {})".format(fmt(r["cash_paid"]-r["cash_refund"],""),fmt(r["card_paid"]-r["card_refund"],""))
                wr.writerow([r["id"],r["sale_no"],r["created_at"],r["display_name"],pay,r["total_cents"],r["cost"],r["total_cents"]-r["cost"]])
        messagebox.showinfo("ToDo","Export terminé.",parent=self)
