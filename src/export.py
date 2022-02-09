# export.py

from fpdf import FPDF, HTMLMixin

def numberFormat(value):
    return "{:,.2f}".format(int(value))


class PDF(FPDF, HTMLMixin):
    def __init__(self) -> None:
        super().__init__(orientation='P', unit='mm')

    def lines(self):
        self.rect(5.0, 5.0, 200.0,287.0)

    def titles(self, text:str):
        self.set_xy(0.0,0.0)
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(0, 0, 0)
        self.cell(w=210.0, h=30.0, align='C', txt=text, border=0)

    def template_page(self, page_name:str):
        self.add_page()
        self.start_section(page_name)
        self.set_fill_color(r=180, g=182, b=200)
        self.rect(5.0, 5.0, 200.0,20.0, style='FD')
        self.set_xy(6.0,7.0)
        self.image('static/images/OpenNMS_Horizontal-Logo_Light-BG-retina-website.png', link='', type='', h=7)
        self.set_xy(6.0,16.0)
        self.image('ra_config/logo.png', link='', type='', h=7)
        self.set_xy(160.0,7.0)
        self.image('ra_config/logo_customer.png', link='', type='', h=7)
        self.titles(page_name)

    def add_image(self, image_path:str, x:int, y:int):
        self.set_xy(x, y)
        self.image(image_path, link='', type='', h=100.0)

    def interface_summary(self, summary:dict, x:int, y:int):
        self.set_xy(x,y)
        self.set_font("Helvetica", size=10)
        table_html = """
            <table class="table" width="100%">
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


def generate_pdf(title:str) -> PDF:
    pdf = PDF()
    pdf.template_page(title)
    return pdf
