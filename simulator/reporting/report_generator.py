"""
Mühendislik Raporu Üreticisi (ReportGenerator)
ReportLab ve Matplotlib kullanarak Faz 0.5 Sözleşme 4 ve Sözleşme 5'e
tam uyumlu, zengin grafikli PDF sertifikasyon-öncesi değerlendirme raporu üretir.
"""

from typing import Dict, Any, Optional
import os
import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether, PageBreak
from reportlab.lib.units import inch, cm

from simulator.core.solver import SimulationResult
from simulator.core.propagation_evaluator import PropagationEvaluation

class ReportGenerator:
    """Termal Kaçak Mühendislik Değerlendirme Raporu PDF Üreticisi."""

    def __init__(self, output_dir: str = "reports"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def _generate_temperature_plot(self, result: SimulationResult, T_onset_C: float = 155.0, T_trigger_C: float = 210.0) -> bytes:
        """Tüm hücrelerin zamana bağlı sıcaklık eğrilerini çizer."""
        fig, ax = plt.subplots(figsize=(7.2, 3.2), dpi=150)
        time_pts = result.time_points_s

        for cell_id, temps in result.temperature_history_C.items():
            cell_name = result.cell_summaries[cell_id]["name"]
            is_trigger = (cell_id == result.pack_metrics.get("trigger_cell_id", 0))
            if is_trigger:
                ax.plot(time_pts, temps, label=f"{cell_name} (Tetikleyici)", color="#d9534f", linewidth=2.4, zorder=5)
            else:
                ax.plot(time_pts, temps, label=cell_name, alpha=0.75, linewidth=1.2)

        # Onset ve Trigger eşik çizgileri (kimyaya göre dinamik)
        ax.axhline(T_onset_C, color="#f0ad4e", linestyle="--", linewidth=1.0, label=f"T_onset ({T_onset_C:.0f}°C)")
        ax.axhline(T_trigger_C, color="#d9534f", linestyle=":", linewidth=1.0, label=f"T_trigger ({T_trigger_C:.0f}°C)")

        ax.set_title("Zamana Bağlı Hücre Sıcaklık Dağılımı (°C)", fontsize=11, fontweight="bold", pad=8)
        ax.set_xlabel("Zaman (s)", fontsize=9)
        ax.set_ylabel("Sıcaklık (°C)", fontsize=9)
        ax.grid(True, linestyle="--", alpha=0.4)
        ax.legend(loc="upper left", fontsize=6, ncol=3)
        fig.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()

    def _generate_heatmap_plot(self, result: SimulationResult) -> bytes:
        """Modül hücrelerinin 2D yerleşimi ve pik sıcaklık haritasını çizer."""
        fig, ax = plt.subplots(figsize=(6.0, 3.0), dpi=150)

        cells = result.cell_summaries
        x_coords = [c["pos_x_mm"] for c in cells]
        y_coords = [c["pos_y_mm"] for c in cells]
        max_temps = [c["max_temperature_C"] for c in cells]

        scatter = ax.scatter(
            x_coords, y_coords,
            c=max_temps,
            cmap="inferno",
            s=350,
            edgecolors="#333333",
            linewidths=1.2,
            vmin=25,
            vmax=max(max_temps) if max(max_temps) > 100 else 100
        )

        for c in cells:
            ax.text(
                c["pos_x_mm"], c["pos_y_mm"],
                f"{c['cell_id']}\n{int(c['max_temperature_C'])}°C",
                ha="center", va="center",
                fontsize=7,
                fontweight="bold",
                color="white" if c["max_temperature_C"] > 250 else "black"
            )

        cbar = fig.colorbar(scatter, ax=ax)
        cbar.set_label("Pik Sıcaklık (°C)", fontsize=8)
        ax.set_title("Modül 2D Pik Sıcaklık Isı Haritası", fontsize=10, fontweight="bold", pad=8)
        ax.set_xlabel("X Konumu (mm)", fontsize=8)
        ax.set_ylabel("Y Konumu (mm)", fontsize=8)
        ax.grid(True, linestyle=":", alpha=0.4)
        fig.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()

    def generate_pdf_report(
        self,
        result: SimulationResult,
        eval_result: PropagationEvaluation,
        report_filename: Optional[str] = None
    ) -> str:
        """Tam kapsamlı mühendislik değerlendirme PDF raporu oluşturur."""
        filename = report_filename or f"Thermal_Runaway_Report_{result.job_id}.pdf"
        filepath = os.path.join(self.output_dir, filename)

        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            rightMargin=1.5 * cm,
            leftMargin=1.5 * cm,
            topMargin=1.5 * cm,
            bottomMargin=1.5 * cm
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "TitleStyle",
            parent=styles["Heading1"],
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#1e293b"),
            fontName="Helvetica-Bold"
        )
        subtitle_style = ParagraphStyle(
            "SubTitleStyle",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#475569")
        )
        section_style = ParagraphStyle(
            "SectionStyle",
            parent=styles["Heading2"],
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#0f172a"),
            fontName="Helvetica-Bold",
            spaceBefore=10,
            spaceAfter=6
        )
        body_style = ParagraphStyle(
            "BodyStyle",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#334155")
        )
        disclaimer_style = ParagraphStyle(
            "DisclaimerStyle",
            parent=styles["Normal"],
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#b91c1c"),
            fontName="Helvetica-Bold"
        )

        story = []

        # 1. Başlık ve Doküman Bilgisi
        story.append(Paragraph("PİL PAKETİ TERMAL KAÇAK YAYILIMI SİMÜLASYON RAPORU", title_style))
        story.append(Paragraph("Mühendislik Ön-Değerlendirmesi / Pre-Certification Screening (UL 9540A)", subtitle_style))
        story.append(Spacer(1, 0.3 * cm))

        # Yasal ve Regülasyon Feragat Uyarısı (Sözleşme 4.2)
        disclaimer_text = (
            "DİKKAT: Bu rapor resmi bir laboratuvar sertifikası (UL/TÜV) niteliğinde değildir. "
            "Fiziksel test öncesi pack tasarımındaki yayılım zafiyetlerini tespit etmek amacıyla hazırlanmış bir "
            "Mühendislik Ön-Değerlendirme (Engineering Assessment) çalışmasıdır."
        )
        story.append(Table(
            [[Paragraph(disclaimer_text, disclaimer_style)]],
            colWidths=[17.5 * cm],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fef2f2")),
                ("BORDER", (0, 0), (-1, -1), 1, colors.HexColor("#fca5a5")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ])
        ))
        story.append(Spacer(1, 0.2 * cm))

        # Dinamik Güvenlik (Confidence) Uyarısı
        if getattr(eval_result, "confidence_level", "high") == "low":
            story.append(Table(
                [[Paragraph(eval_result.confidence_message, disclaimer_style)]],
                colWidths=[17.5 * cm],
                style=TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fef9c3")),
                    ("BORDER", (0, 0), (-1, -1), 1, colors.HexColor("#fde047")),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ])
            ))
        story.append(Spacer(1, 0.3 * cm))

        # 2. İzlenebilirlik Mührü Tablosu (Sözleşme 3 & 4)
        trace_data = [
            ["İş ID (Job ID)", result.job_id, "Tarih / Saat", result.created_at],
            ["Config Hash (SHA-256)", result.config_hash[:24] + "...", "Parmak İzi", result.execution_fingerprint],
            ["Doğrulama Durumu", result.validation_status, "Çözücü Yöntemi", result.solver_metadata.get("solver_method", "LSODA")]
        ]
        t_trace = Table(trace_data, colWidths=[3.5 * cm, 5.25 * cm, 3.5 * cm, 5.25 * cm])
        t_trace.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1e293b")),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ]))
        story.append(t_trace)
        story.append(Spacer(1, 0.4 * cm))

        # 3. Yönetici Özeti ve Çok Boyutlu Risk Vektörü (Sözleşme 4.3)
        story.append(Paragraph("1. Çok Boyutlu Yayılım Risk Değerlendirmesi", section_style))

        status_color = "#16a34a" if eval_result.status.value == "NO_PROPAGATION" else (
            "#d97706" if eval_result.status.value == "LOCAL_CONTAINED" else "#dc2626"
        )

        risk_data = [
            ["Yayılım Sınıfı", eval_result.status.value, "Yayılım Oranı", f"%{eval_result.propagation_ratio*100:.1f}"],
            ["İlk Yayılma Süresi (t_prop1)", f"{eval_result.time_to_first_propagation_s or 'YAYILMADI'} s", "Kaçağa Giren Hücre", f"{eval_result.affected_cells_count} / {eval_result.total_cells}"],
            ["Maksimum Modül Sıcaklığı", f"{eval_result.peak_module_temp_C:.1f} °C", "Güvenlik Marjı (Margin)", f"{eval_result.min_containment_margin_C:.1f} °C"],
            ["Risk Skoru (100 üzerinden)", f"{eval_result.risk_score_100:.1f} / 100", "Belirsizlik Bandı", "±10°C / ±12% süre"]
        ]
        t_risk = Table(risk_data, colWidths=[4.2 * cm, 4.55 * cm, 4.2 * cm, 4.55 * cm])
        t_risk.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ffffff")),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0f172a")),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
            ("TEXTCOLOR", (1, 0), (1, 0), colors.HexColor(status_color)),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t_risk)
        story.append(Spacer(1, 0.2 * cm))

        story.append(Paragraph(f"<b>Sonuç Değerlendirmesi:</b> {eval_result.regulatory_summary}", body_style))
        story.append(Spacer(1, 0.4 * cm))

        # 4. Grafikler (Sıcaklık Eğrileri ve 2D Isı Haritası)
        story.append(Paragraph("2. Termal Yayılım Grafikleri ve Isı Haritası", section_style))

        # Kimyaya göre dinamik eşik sıcaklıklarını belirle
        _chem_onsets = {"NMC_generic_v1": 155.0, "NMC811_high_energy_v1": 138.0, "LFP_generic_v1": 215.0}
        _chem_triggers = {"NMC_generic_v1": 210.0, "NMC811_high_energy_v1": 190.0, "LFP_generic_v1": 280.0}
        first_chem = result.cell_summaries[0].get("chemistry_id", "NMC_generic_v1") if result.cell_summaries else "NMC_generic_v1"
        t_onset = _chem_onsets.get(first_chem, 155.0)
        t_trigger = _chem_triggers.get(first_chem, 210.0)

        temp_plot_bytes = self._generate_temperature_plot(result, T_onset_C=t_onset, T_trigger_C=t_trigger)
        heatmap_plot_bytes = self._generate_heatmap_plot(result)

        temp_img = Image(io.BytesIO(temp_plot_bytes), width=17.5 * cm, height=7.5 * cm)
        heatmap_img = Image(io.BytesIO(heatmap_plot_bytes), width=14.0 * cm, height=7.0 * cm)

        story.append(temp_img)
        story.append(Spacer(1, 0.3 * cm))
        story.append(heatmap_img)
        story.append(PageBreak())

        # 5. Hücre Bazlı Detay Olay Tablosu
        story.append(Paragraph("3. Hücre Olay ve Tepe Sıcaklık Özeti", section_style))
        cell_table_data = [["Hücre", "Kimya", "Konum (mm)", "T_max (°C)", "T_onset (s)", "T_runaway (s)", "Durum"]]

        for c in result.cell_summaries:
            onset_str = f"{c['onset_time_s']:.2f}" if c.get("onset_time_s") else "-"
            runaway_str = f"{c['runaway_time_s']:.2f}" if c.get("runaway_time_s") else "-"
            cell_table_data.append([
                c["name"],
                c["chemistry_id"],
                f"({c['pos_x_mm']}, {c['pos_y_mm']})",
                f"{c['max_temperature_C']:.1f}",
                onset_str,
                runaway_str,
                c["state"]
            ])

        t_cells = Table(cell_table_data, colWidths=[2.5 * cm, 3.2 * cm, 3.0 * cm, 2.3 * cm, 2.3 * cm, 2.3 * cm, 1.9 * cm])
        t_cells.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("ALIGN", (3, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(t_cells)

        # PDF oluştur
        doc.build(story)
        return filepath
