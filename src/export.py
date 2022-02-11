# export.py

from fpdf import FPDF, HTMLMixin
from datetime import datetime
import trending
import plotly

def numberFormat(value):
    return "{:,.2f}".format(int(value))

class PDF(FPDF, HTMLMixin):
    def __init__(self) -> None:
        super().__init__(orientation='P', unit='mm')

    def lines(self):
        self.rect(5.0, 5.0, 200.0,287.0)

    def titles(self, title:str):
        self.set_xy(5.0,11.0)
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(0, 0, 0)
        self.cell(w=200.0, h=18.0, align='C', txt=title, border=0)

    def footer(self):
        self.set_y(-10)

        self.set_font('Helvetica', size=8)
        self.set_text_color(0, 0, 0)

        # Add a page number
        page = 'Page ' + str(self.page_no()) + '/{nb}'
        self.cell(0, 10, page, 0, 0, 'C')
        self.cell(0, 10, align='R', txt=self.created.strftime("%m/%d/%Y, %H:%M:%S"), border=0)

    def template_page(self, pair_name:str, page_name:str):
        self.add_page()
        self.start_section(page_name)
        self.set_fill_color(r=180, g=182, b=200)
        self.rect(5.0, 5.0, 200.0,20.0)
        self.set_xy(8.0,7.0)
        self.image('static/images/OpenNMS_Horizontal-Logo_Light-BG-retina-website.png', link='', type='', h=7)
        self.set_xy(90.0,7.0)
        self.image('ra_config/logo.png', link='', type='', h=7)
        self.set_xy(160.0,7.0)
        self.image('ra_config/logo_customer.png', link='', type='', h=7)
        self.titles(f"""{pair_name}     {page_name}""")

    def add_image(self, image_path:str, x:int, y:int):
        self.set_xy(x, y)
        self.image(image_path, link='', type='', h=100.0)

    def interface_summary(self, summary:dict, x:int, y:int):
        self.set_xy(x,y)
        self.set_font("Helvetica", size=10)
        table_html = """
            <table class="table" width="75%">
                    <tr>
                    <th width="20%">Metric</th>
                    <th width="20%">Min</th>
                    <th width="20%">Mean</th>
                    <th width="20%">Max</th>
                    <th width="20%">Total</th>
                </tr>"""
        for  metric in summary:
            table_html += f"<tr><td>{metric}</td>"
            table_html += f'<td align="right"><font face="Courier">{numberFormat(summary[metric]["Min"])}</font></td>'
            table_html += f'<td align="right"><font face="Courier">{numberFormat(summary[metric]["Average"])}</font></td>'
            table_html += f'<td align="right"><font face="Courier">{numberFormat(summary[metric]["Max"])}</font></td>'
            table_html += f'<td align="right"><font face="Courier">{numberFormat(summary[metric]["Total"])}</font></td></tr>'
        table_html += "</table>"
        self.write_html(table_html)

    def top_n_summary(self, top_n:dict, x:int, y:int):
        self.set_xy(x,y)
        self.set_font("Helvetica", size=10)
        table_html = f'<table width="75%">'
        for metric in top_n:
            table_html += f'<tr>'
            table_html += f'<th width="50%">VIP</th>'
            table_html += f'<th width="50%">{metric}</th>'
            table_html += f'</tr>'
            for site in top_n[metric]:
                table_html += f'<tr>'
                table_html += f'<td>{site}</td>'
                table_html += f'<td align="right"><font face="Courier">{numberFormat(top_n[metric][site])}</font></td>'
                table_html += f'</tr>'
        table_html += f'</table>'
        self.write_html(table_html)

def generate_pdf(pair:str='', title:str='', date_stamp:datetime=datetime.now()) -> PDF:
    pdf = PDF()
    pdf.created = date_stamp
    pdf.template_page(pair, title)
    return pdf

def render_node_pdf(pair_name:str, vips:list, parsed_metrics:dict, metrics:list) -> PDF:
    pdf = generate_pdf(pair_name, 'Summary', parsed_metrics['node[data]']['generated'])
    pdf.interface_summary(parsed_metrics['node[device]']['stats'], 10, 30)
    pdf.top_n_summary(parsed_metrics['node[top_n]'], 10, 70)
    for vip in vips:
        interface = '/Common/' + vip
        weekends = trending.find_weekends(parsed_metrics, interface)
        trend_time = trending.time_trend(parsed_metrics, interface, metrics)
        trend_line = trending.time_lines(parsed_metrics, interface, metrics)

        fig1 = trending.get_trend_graph(trend_time)
        fig2 = trending.get_trend_line(trend_line[0], trend_line[1], weekends)

        pdf.template_page(pair_name, vip)
        pdf.interface_summary(parsed_metrics[interface]['stats'], 10, 30)

        plotly.io.write_image(fig1, file=f"temp/fig-{vip.replace('/','-')}-1.png", format='png', width=900, height=500)
        pdf.add_image(f"temp/fig-{vip.replace('/','-')}-1.png", 10, 70)
        plotly.io.write_image(fig2, file=f"temp/fig-{vip.replace('/','-')}-2.png", format='png', width=900, height=500)
        pdf.add_image(f"temp/fig-{vip.replace('/','-')}-2.png", 10, 170)

    return pdf

def render_vip_pdf(pair_name:str, vip:str, parsed_metrics:dict, metrics:list) -> PDF:
    interface = '/Common/' + vip
    weekends = trending.find_weekends(parsed_metrics, interface)
    trend_time = trending.time_trend(parsed_metrics, interface, metrics)
    trend_line = trending.time_lines(parsed_metrics, interface, metrics)

    fig1 = trending.get_trend_graph(trend_time)
    fig2 = trending.get_trend_line(trend_line[0], trend_line[1], weekends)

    plotly.io.write_image(fig1, file=f"temp/fig-{vip.replace('/','-')}-1.png", format='png', width=900, height=500)
    plotly.io.write_image(fig2, file=f"temp/fig-{vip.replace('/','-')}-2.png", format='png', width=900, height=500)

    pdf = generate_pdf(pair_name, vip, parsed_metrics['node[data]']['generated'])
    pdf.interface_summary(parsed_metrics[interface]['stats'], 10, 30)
    pdf.add_image(f"temp/fig-{vip.replace('/','-')}-1.png", 10, 70)
    pdf.add_image(f"temp/fig-{vip.replace('/','-')}-2.png", 10, 170)

    return pdf
