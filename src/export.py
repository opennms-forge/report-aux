# export.py

# PDF generation

from requests.auth import HTTPBasicAuth
from fpdf import FPDF, HTMLMixin
from datetime import datetime
import trending
import plotly
import json
import ra_processing
import time
import shutil
import os


def numberFormat(value: float, round: int = 2) -> str:
    """Formats numbers with commas and decimals

    Args:
        value (float): Number to format
        round (int, optional): Number of decimals to round. Defaults to 2.

    Returns:
        str: String representation of formatted number
    """
    num_format = "{:,." + str(round) + "f}"
    return num_format.format(float(value))


class PDF(FPDF, HTMLMixin):
    def __init__(self) -> None:
        super().__init__(orientation="P", unit="mm", format="letter")

    def titles(self, title: str):
        """Add heading to page

        Args:
            title (str): Page title
        """
        self.set_xy(5.0, 11.0)
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(0, 0, 0)
        self.cell(w=self.w - 10, h=18.0, align="C", txt=title, border=0)

    def footer(self):
        """Override footer function to add page numbers"""
        self.set_y(-10)

        self.set_font("Helvetica", size=8)
        self.set_text_color(0, 0, 0)

        # Add a page number
        if hasattr(self, "report_time"):
            text = f'Report Covers: {self.report_time["start"].strftime("%m/%d/%Y")} to {self.report_time["end"].strftime("%m/%d/%Y")}'
        else:
            text = f'Generated: {self.created.strftime("%m/%d/%Y, %H:%M:%S")}'
        page = "Page " + str(self.page_no()) + "/{nb}"
        self.set_x(5)
        self.cell(w=self.w - 10, h=5, align="R", txt=page, border=0)
        self.set_x(5)
        self.cell(w=self.w - 10, h=5, align="L", txt=text, border=0)
        self.set_x(5)
        self.cell(w=self.w - 10, h=5, align="C", txt="Generated by OpenNMS®", border=0)

    def template_page(self, pair_name: str, page_name: str):
        """Add page to PDF with consistent theme

        Args:
            pair_name (str): Name of node pair
            page_name (str): Name of page
        """
        self.add_page()
        self.start_section(page_name)
        self.set_fill_color(r=180, g=182, b=200)
        self.rect(5.0, 5.0, self.w - 10, 20.0)
        self.set_xy(8.0, 7.0)
        # self.image('static/images/OpenNMS_Horizontal-Logo_Light-BG-retina-website.png', link='', type='', h=7)
        # self.set_xy((self.w/2)-25,7.0)
        self.image("ra_config/logo_customer.png", link="", type="", h=7)
        self.set_xy(self.w - 51, 7.0)
        self.image("ra_config/logo.png", link="", type="", h=7)
        self.titles(f"""{pair_name}     {page_name}""")

    def add_image(self, image_path: str, x: float, y: float):
        """Add image to current page

        Args:
            image_path (str): Path to image file
            x (int): X coordinate of image
            y (int): Y coordinate of image
        """
        self.set_xy(x, y)
        self.image(image_path, link="", type="", w=self.w - (x * 2))

    def interface_summary(self, summary: dict, x: float, y: float):
        """Add interface summary to page

        Args:
            summary (dict): VIP summary from parsed metrics
            x (int): X coordinate of table
            y (int): Y coordinate of table
        """
        self.set_xy(x, y)
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
        for metric in summary:
            table_html += f"<tr><td>{metric}</td>"
            table_html += f'<td align="right"><font face="Courier">{numberFormat(summary[metric]["Min"])}</font></td>'
            table_html += f'<td align="right"><font face="Courier">{numberFormat(summary[metric]["Average"])}</font></td>'
            table_html += f'<td align="right"><font face="Courier">{numberFormat(summary[metric]["Max"])}</font></td>'
            table_html += f'<td align="right"><font face="Courier">{numberFormat(summary[metric]["Total"])}</font></td></tr>'
        table_html += "</table>"
        self.write_html(table_html)

    def top_n_summary(self, pair_name: str, parsed_metrics: dict, x: float, y: float):
        """Add page to PDF with top N summary

        Args:
            pair_name (str): Name of node pair
            top_n (dict): Name of metric and top N values
            x (int): X coordinate of table
            y (int): Y coordinate of table
        """
        top_n = parsed_metrics["node[top_n]"]
        self.set_xy(x, y)
        self.set_font("Helvetica", size=10)
        for metric in top_n:
            if top_n[metric]:
                self.template_page(pair_name, f"Top VIPs: {metric}")
                table_html = '<table width="100%">'
                table_html += "<tr>"
                table_html += '<th width="34%">VIP</th>'
                table_html += f'<th width="33%">Average {metric}</th>'
                table_html += f'<th width="33%">Peak {metric}</th>'
                table_html += "</tr>"
                for site in top_n[metric]:
                    table_html += "<tr>"
                    if "/" in site:
                        table_html += f'<td>{site.rsplit("/", 1)[1]}</td>'
                    else:
                        table_html += f"<td>{site}</td>"
                    table_html += f'<td align="right"><font face="Courier">{numberFormat(top_n[metric][site])}</font></td>'
                    table_html += '<td align="right"><font face="Courier">'
                    table_html += f'{numberFormat(parsed_metrics[site]["stats"][metric]["Max"])}</font></td>'
                    table_html += "</tr>"
                table_html += "<tr><td> </td><td> </td></tr>"
                table_html += "</table>"
                self.write_html(table_html)


def generate_pdf(
    pair: str = "",
    title: str = "",
    date_stamp: datetime = datetime.now(),
    report_time: dict = {},
) -> PDF:
    """Create new PDF object

    Args:
        pair (str, optional): Node pair name. Defaults to ''.
        title (str, optional): First page's title. Defaults to ''.
        date_stamp (datetime, optional): Timestamp for footer. Defaults to datetime.now().
        report_time (dict, optional): Time range for report data for footer. Defaults to {}.

    Returns:
        PDF: PDF with blank first page
    """
    pdf = PDF()
    pdf.created = date_stamp
    if report_time:
        pdf.report_time = report_time
    pdf.template_page(pair, title)
    return pdf


def render_vip_pdf(
    pair_name: str, vip: str, parsed_metrics: dict, metrics: list, pdf: PDF = None
) -> PDF:
    """Add VIP page to existing last page of PDF

    Args:
        pair_name (str): Node pair name
        vip (str): VIP name
        parsed_metrics (dict): Data to include on the page
        metrics (list): List of metrics to include on the page
        pdf (PDF, optional): PDF object to use.
        Will create new PDF if None.
        Defaults to None.

    Returns:
        PDF: PDF with VIP summary added
    """
    if not pdf:
        pdf = generate_pdf(
            pair_name,
            vip,
            parsed_metrics["node[data]"]["generated"],
            parsed_metrics["node[data]"]["range"],
        )
    if vip != "Summary":
        interface = "/Common/" + vip
        if "/" in vip:
            vip = vip.rsplit("/", 1)[1]
    else:
        interface = "node[device]"
    print(f"Rendering {pair_name}:{vip} PDF page")
    pdf.interface_summary(parsed_metrics[interface]["stats"], 10, 30)
    weekends = trending.find_weekends(parsed_metrics, interface)
    trend_time = trending.time_trend(parsed_metrics, interface, metrics)
    trend_line = trending.time_lines(parsed_metrics, interface, metrics)

    fig1 = trending.get_trend_graph(trend_time, margin=10)
    fig2 = trending.get_trend_line(trend_line[0], trend_line[1], weekends, margin=10)

    plotly.io.write_image(
        fig1,
        file=f"temp/fig-{vip.replace('/','-')}-1.png",
        format="png",
        width=1350,
        height=600,
    )
    pdf.add_image(f"temp/fig-{vip.replace('/','-')}-1.png", 10, 75)
    plotly.io.write_image(
        fig2,
        file=f"temp/fig-{vip.replace('/','-')}-2.png",
        format="png",
        width=1350,
        height=600,
    )
    pdf.add_image(f"temp/fig-{vip.replace('/','-')}-2.png", 10, 170)
    return pdf


def render_node_pdf(
    pair_name: str, vips: list, parsed_metrics: dict, metrics: list
) -> PDF:
    """Geneate PDF for all VIPs on a node pair

    Args:
        pair_name (str): Node pair name
        vips (list): List of VIPs to include on the report
        parsed_metrics (dict): Data to include on the page
        metrics (list): List of metrics to include on the page

    Returns:
        PDF: PDF with all VIPs added
    """
    pdf = generate_pdf(
        pair_name,
        "Summary",
        parsed_metrics["node[data]"]["generated"],
        parsed_metrics["node[data]"]["range"],
    )
    # pdf.interface_summary(parsed_metrics['node[device]']['stats'], 10, 30)
    pdf = render_vip_pdf(pair_name, "Summary", parsed_metrics, metrics, pdf)
    pdf.top_n_summary(pair_name, parsed_metrics, 10, 22)
    for vip in vips:
        # interface = "/Common/" + vip
        pdf.template_page(pair_name, vip)
        pdf = render_vip_pdf(pair_name, vip, parsed_metrics, metrics, pdf)

    return pdf


def render_all_nodes_pdf() -> None:
    """Generate PDF for all node pairs"""
    start_time = time.time()
    f = open("ra_config/config.json")
    config = json.load(f)
    f.close()
    RA_url = config["url"]
    RAauth = HTTPBasicAuth(config["username"], config["password"])
    loop_count = 0
    vip_count = 0
    clear_report_temp()
    for pair in config["nodes"]:
        interfaces = []
        metrics = []
        name = []
        loop_count += 1

        for node in pair:
            interface_list = ra_processing.get_interfaces(RA_url, RAauth, node)
            name.append(interface_list["label"].split(" ")[1][1:-1])
            interfaces_a, metrics_a = ra_processing.filter_interfaces(interface_list)
            [
                interfaces.append(interface)
                for interface in interfaces_a
                if interface not in interfaces
            ]
            [metrics.append(metric) for metric in metrics_a if metric not in metrics]

        pair_name = ":".join(name)
        parsed_metrics = ra_processing.main(RA_url, RAauth, interfaces, metrics)
        print(f"Collected data for {pair_name}")
        vip_count += parsed_metrics["node[data]"]["count"]
        byte_metrics = trending.byte_metrics(metrics)
        vips = [
            vip.replace("/Common/", "") for vip in parsed_metrics if "/Common/" in vip
        ]
        if vips:
            pdf = render_node_pdf(
                pair_name=pair_name,
                vips=vips,
                parsed_metrics=parsed_metrics,
                metrics=byte_metrics,
            )
        filename = f"{pair_name.replace(':','_')}_{datetime.fromtimestamp(start_time).strftime('%Y_%m_%d_%H_%M')}.pdf"
        pdf.output(f"static/pdf/{filename}", "F")
        print(f"Rendered {pair_name} PDF")

    shutil.make_archive(
        f"static/all_pairs_{datetime.fromtimestamp(start_time).strftime('%Y_%m_%d_%H_%M')}",
        "zip",
        "static/pdf/",
    )
    end_time = time.time()
    print(
        f"Time to process {loop_count} pairs with {vip_count} VIPs: {end_time - start_time}"
    )


def clear_report_temp() -> None:
    """Clear all cached report files"""
    zip_files = os.scandir("static")
    for file in zip_files:
        if ".zip" in file.name:
            os.remove(file.path)
    pdf_files = os.scandir("static/pdf")
    for file in pdf_files:
        if ".pdf" in file.name:
            os.remove(file.path)
