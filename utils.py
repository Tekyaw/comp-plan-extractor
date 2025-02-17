import pdfplumber
from thefuzz import fuzz
from thefuzz import process
from pprint import pprint
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
import re


@dataclass
class CompPlanScraper:
    page: pdfplumber.page.Page
    height: float
    width: float

    #################################
    # bbox_rules = (x0, y0, x1, y1) #
    #################################

    def parse_col_coordinates(self):
        cord_roles, cols = [], []
        contents = self.page.extract_text_lines()

        for content in contents:
            if (top := content["top"]) >= 100 and (bottom := content["bottom"]) <= self.height - 50:
                title_text = ""
                for char in content["chars"]:
                    if "bold" in char.get("fontname").lower():
                        char_text = char.get("text")
                        title_text += char_text
                cord_roles.append(title_text.strip())
                x0 = content["x0"]
                cols.append(x0)
                
        cols.append(self.width)
        cols = sorted(list(set(cols)))
        cord_roles = [role for role in cord_roles if role != ""]
        return cord_roles, cols

    def parse_text_within_bbox(self, bbox_rules):
        text = self.page.within_bbox(bbox_rules).extract_text()
        return text

    def parse_doc_title(self):
        title_bbox = (0, 20, self.page.width, 120) 
        title = self.parse_text_within_bbox(title_bbox)
        return title

    def parse_comp_plan_roles(self):
        cord_roles, cols = self.parse_col_coordinates()

        roles = []
        for i in range(len(cols))[:-1]:
            x0, x1, y0, y1 = cols[i], cols[i+1], 120, self.height - 50
            role = self.parse_text_within_bbox((x0, y0, x1, y1))
            roles.extend(role.split("\n"))
        
        roles = list(map(lambda x: x.strip(), roles))

        roles_with_titles = {}
        current_title = ""
        for role in roles:
            matches = process.extract(role, cord_roles, scorer=fuzz.ratio)
            if matches[0][1] > 90:
                if current_title == role:
                    roles_with_titles[current_title].append(role)
                else:
                    current_title = role
                    roles_with_titles.setdefault(current_title, [])
            else:
                roles_with_titles[current_title].append(role)
        return roles_with_titles

@dataclass
class CompPlanDetails(CompPlanScraper): 
            
    def parse_details_title(self, merged_page=False):
        if not merged_page:
            metric_bucket_info = 70
        else:
            metric_bucket_info = self.page.search("Metric Bucket")[0]["top"]
        title_bbox = (0, metric_bucket_info - 50, self.page.width / 2, metric_bucket_info + 10)  
        title = self.parse_text_within_bbox(title_bbox)
        try:
            title_type = [item["chars"][0].get("fontname") for item in self.page.within_bbox(title_bbox).extract_text_lines()][0]
        except:
            title_type = "None"
        return (title, title_type)

    def parse_attainment_modifiers(self):
        attainment_modifiers_table_details = [(content["top"], content["x0"]) for content in self.page.search("Attainment Modifiers")][-1] # (top, x0)
        attainment_modifiers = self.page.within_bbox((attainment_modifiers_table_details[1]-30, attainment_modifiers_table_details[0], self.width - 100, self.height)).extract_tables()
        attainment_modifiers_all = []
        for attainment_modifier in attainment_modifiers:
            attainment_modifiers_all.extend(attainment_modifier)
        return attainment_modifiers_all
    
    def parse_remaining_attainment_modifiers(self):
        attainment_modifiers = self.page.within_bbox((0, 20, self.width, self.height)).extract_table()  
        return attainment_modifiers

    def parse_metric_bucket(self):
        metric_title = [(content["top"], content["x0"]) for content in self.page.search("Metric Bucket")][0]
        try:
            attainment_modifiers_title = [(content["top"], content["x0"]) for content in self.page.search("Attainment Modifiers")][0]
        except IndexError:
            attainment_modifiers_title = [self.height]
        paycurve_title = [(content["top"], content["x0"]) for content in self.page.search("PayCurve")][0]
        contents = self.page.within_bbox((metric_title[1], metric_title[0], paycurve_title[1], attainment_modifiers_title[0])).extract_tables()
        return contents

    def parse_paycurve(self):
        paycurve_table_details = [(content["top"], content["x0"]) for content in self.page.search("PayCurve")][-1] # (top, x0)
        paycurve = self.page.within_bbox((paycurve_table_details[1]-80, paycurve_table_details[0], paycurve_table_details[1] + 150, paycurve_table_details[0]+120)).extract_table()
        return paycurve

    def parse_gate_text(self):
        gate_text_table_details = [(content["top"], content["x0"]) for content in self.page.search("Gate Text")][-1] # (top, x0)
        gate_text = self.page.within_bbox((gate_text_table_details[1]-80, gate_text_table_details[0], gate_text_table_details[1] + 150, gate_text_table_details[0]+100)).extract_text()
        return " ".join([content for content in gate_text.split("\n") if content != "" ])

    def parse_quota_cadence(self):
        quota_cadence_table_details = [(content["top"], content["x0"]) for content in self.page.search("Quota Cadence")][-1] # (top, x0)
        quota_cadence = self.page.within_bbox((quota_cadence_table_details[1]-80, quota_cadence_table_details[0], quota_cadence_table_details[1] + 150, quota_cadence_table_details[0]+100)).extract_text()
        return " ".join([content for content in quota_cadence.split("\n") if content != "" ]).replace("Quota Cadence ", "")

    def parse_unbalanced(self):
        unbalanced_table_details = [(content["top"], content["x0"]) for content in self.page.search("Unbalanced")][0] # (top, x0)
        unbalanced = self.page.within_bbox((unbalanced_table_details[1]-80, unbalanced_table_details[0], self.width, unbalanced_table_details[0]+200)).extract_text()
        return " ".join([content for content in unbalanced.split("\n") if content != "" ]).replace("Unbalanced ", "").replace("Other Information", "")

    def parse_other_information(self):
        metric_bucket_info = self.page.search("Metric Bucket")[0]["top"]
        other_information_table_details = [(content["top"], content["x0"]) for content in self.page.within_bbox((0, metric_bucket_info, self.width, self.height)).search("Other Information")][0] # (top, x0)
        try:
            other_information = self.page.within_bbox((other_information_table_details[1]-50, other_information_table_details[0], self.width, other_information_table_details[0]+300)).extract_text() 
        except ValueError:
            other_information = self.page.within_bbox((other_information_table_details[1]-50, other_information_table_details[0], self.width, self.height)).extract_text()
        return " ".join([content for content in other_information.split("\n") if content != "" ]).replace("Other Information ", "")

    def get_remaining_text_x0s(self, remaining_rows):
        remaining_text_x0s = []
        for remaining_row in remaining_rows:
            if "dell.com:" not in (remaining_text := remaining_row["text"]):
                remaining_text_x0 = remaining_row["x0"]
                remaining_text_x0s.append((remaining_text_x0, remaining_text))
        remaining_text_x0s = sorted(remaining_text_x0s, key=lambda x: x[0])
        return remaining_text_x0s

    def parse_product_eligibility(self, last_page=False):
        product_eligibility_table_details = [(content["top"], content["x0"]) for content in self.page.search("Product Eligibility")][-1] # (top, x0)
        table_start_xs = [l1["x0"] for l1 in self.page.search("L1 Type")]  
        potential_boundaries = ["Other Information", "error has occurred"]
        boundary = None
        for potential_boundary in potential_boundaries:
            try:
                boundary = self.page.search(potential_boundary)[0]["x0"]
                break
            except IndexError:
                pass
        if not boundary:
            boundary = self.width
        table_start_xs.append(boundary)
        all_cols_infos = []
        pe_dfs = []
        for idx in range(len(table_start_xs)-1):
            x0, x1 = table_start_xs[idx], table_start_xs[idx+1]
            top_boundary = self.page.search("Click on Metric names")[0]["top"]
            left_shift = 100
            top_shift = 100
            product_eligibility = self.page.within_bbox((0 if idx == 0 else x0 - left_shift, top_boundary, x1, self.page.bbox[3])).extract_table()
            pe_df = pd.DataFrame(product_eligibility)
            pe_df.columns = pe_df.iloc[0, :].ffill()
            # print(pe_df)
            try:
                pe_df = pe_df.iloc[1:, :]
                pe_df = pe_df.replace("", np.nan).ffill().reset_index(drop=True)
                row_infos = pe_df.iloc[1, :].to_list()
                col_infos = []
                for row in row_infos:
                    try:
                        col_info = self.page.within_bbox((0 if idx == 0 else x0 - left_shift, product_eligibility_table_details[0] - 10, x1, self.page.bbox[3] - 30)).search(row.split("\n")[0])
                        col_infos.append(col_info[0]["x0"])
                    except IndexError:
                        pass
                all_cols_infos.append(col_infos)
                if not len(col_infos) == 0:
                    last_row_infos = product_eligibility[-1]
                    # print(last_row_infos)
                    for last_row_info in last_row_infos:
                        try:
                            last_row_top = [info["top"] for info in self.page.within_bbox((0 if idx == 0 else x0 - left_shift, product_eligibility_table_details[0], x1, self.page.bbox[3] - 30)).search(last_row_info)]
                            break
                        except Exception as e:
                            # print(e)
                            continue
                    last_row_text = " ".join([content for content in product_eligibility[-1] if content != "" and content != None])
                    remaining_row = self.page.within_bbox((0 if idx == 0 else x0 - left_shift, last_row_top[0] + 10, x1, self.page.bbox[3])).extract_text()
                    if "Metric Bucket" not in remaining_row:
                        remaining_row_text = " ".join([content for content in remaining_row.split("\n") if content != "" ])
                        if (similarity := text_comparison(remaining_row_text, last_row_text)) < 10:
                            remaining_rows = self.page.within_bbox((0 if idx == 0 else x0 - left_shift, last_row_top[0] + 10, x1, self.page.bbox[3])).extract_text_lines()
                            remaining_text_x0s = self.get_remaining_text_x0s(remaining_rows)
                            remaining_table = categorize_col_infos(remaining_text_x0s, col_infos)
                            cols = pe_df.columns.tolist()
                            if len(remaining_table) == len(cols):
                                pe_df.columns = range(len(cols))
                                if sum([bool(item) for item in remaining_table]) > 0:
                                    remaining_rows_info = pd.DataFrame(remaining_table, index=pe_df.columns).replace("", np.nan).T
                                    pe_df = pd.concat([pe_df, remaining_rows_info], axis=0).reset_index(drop=True)
                                pe_df.columns = cols
            except IndexError:
                pass
            # print(pe_df)
            # print("==========")
            pe_dfs.append(pe_df)
        return pe_dfs if not last_page else all_cols_infos

    def parse_next_page_product_eligibility(self):
        text_cols = self.get_remaining_text_x0s(self.page.within_bbox((0, 30, self.page.width, self.page.bbox[3])).extract_text_lines())
        return text_cols
    
    def check_if_title_is_empty(self, title) -> bool:
        return len(self.page.search(title)) == 0
    
def return_none_if_empty(func):
    try:
        return func()
    except IndexError:
        return None

def output_to_txt(roles, infos):
    with open("pdf_reader.txt", "w", encoding="utf-8") as f:
        f.write(f"Roles: {roles}\n")
        for info in infos:
            f.write(rf"Information: {info}\n")

def text_comparison(text1, text2):
    return fuzz.ratio(text1, text2)

def categorize_col_infos(col_infos: list[tuple], benchmark_infos: list):
    targeted_cols = [''] * len(benchmark_infos)
    benchmark_infos = sorted(list(set(benchmark_infos)))
    for col_info in col_infos:
        num_col  = 0
        # print(benchmark_infos)
        for benchmark_info in benchmark_infos:
            if col_info[0] >= benchmark_info:
                num_col += 1
        if num_col > 0:
            # print("num of col:",num_col - 1)
            targeted_cols[num_col - 1] += col_info[1] + "\n"
    return [col.strip() for col in targeted_cols]

def parse_content_details(title, comp_plan_details):
    attainment_modifiers = return_none_if_empty(comp_plan_details.parse_attainment_modifiers)
    metric_bucket = return_none_if_empty(comp_plan_details.parse_metric_bucket)
    paycurve = return_none_if_empty(comp_plan_details.parse_paycurve)
    gate_text = return_none_if_empty(comp_plan_details.parse_gate_text)
    quota_cadence = return_none_if_empty(comp_plan_details.parse_quota_cadence)
    unbalanced = return_none_if_empty(comp_plan_details.parse_unbalanced)
    other_information = return_none_if_empty(comp_plan_details.parse_other_information)
    info = {
        "Title": title,
        "Metric Bucket Weightage": metric_bucket,
        "Pay Curve": paycurve,
        "Gate Text": gate_text,
        "Quota Cadence": quota_cadence,
        "Unbalanced": unbalanced,
        "Attainment Modifiers": attainment_modifiers,
        "Other Information": other_information
    }
    return info

def extract_comp_plan_content(file):
    infos = []
    roles = None
    with pdfplumber.open(file) as pdf:
        pages = pdf.pages
        for index, page in list(enumerate(pages))[:]:
            # print(index + 1)
            # print("Extracting Info from page {}".format(index))
            page_scraper = CompPlanScraper(page, page.height, page.width)
            if index == 0:
                roles = page_scraper.parse_comp_plan_roles()
                infos.append({
                        "Document Title":  page_scraper.parse_doc_title(),
                        "Roles Availability": roles
                    })
            else:
                comp_plan_details = CompPlanDetails(page, page.height, page.width)
                title, title_type = comp_plan_details.parse_details_title()
                # print(title)
                if title != "Product Eligibility" and "bold" in title_type.lower():
                    if comp_plan_details.check_if_title_is_empty("Metric Bucket"):
                        last_info = infos[-1]
                        last_info["Attainment Modifiers"] = return_none_if_empty(comp_plan_details.parse_remaining_attainment_modifiers)
                        infos[-1] = last_info
                    else:
                        info = parse_content_details(title, comp_plan_details)
                        infos.append(info)

                elif title == "Product Eligibility" and "bold" in title_type.lower():
                    if comp_plan_details.check_if_title_is_empty("Metric Bucket"):

                        product_eligibility = return_none_if_empty(comp_plan_details.parse_product_eligibility)

                        infos.append({
                            "product_eligibility": product_eligibility
                        })
                    else:
                        product_eligibility = return_none_if_empty(comp_plan_details.parse_product_eligibility)

                        merged_page_new_title = comp_plan_details.parse_details_title(merged_page=True)[0]
                        info = parse_content_details(merged_page_new_title, comp_plan_details)
                        
                        infos.append({
                            "product_eligibility": product_eligibility
                        })
                        infos.append(info)
                        
                else: ## if the page do not have any title or simply do not have anything
                    if title_type == "None":
                        continue
                    num_page_to_last_table = 1
                    while True:
                        try:
                            last_page = pages[index - num_page_to_last_table]
                            last_page_tables = CompPlanDetails(last_page, last_page.height, last_page.width).parse_product_eligibility(last_page=True)
                            break
                        except IndexError:
                            num_page_to_last_table += 1
                    remaining_table = comp_plan_details.parse_next_page_product_eligibility()
                    tables = {}
                    for last_page_table_idx, last_page_table in enumerate(last_page_tables):
                        table = categorize_col_infos(remaining_table, last_page_table)
                        if sum([bool(item) for item in table]) > 0:
                            tables[last_page_table_idx] = table
                    pe_dfs = infos[-1]["product_eligibility"]
                    # print(len(pe_dfs))
                    for table_idx in tables:
                        pe_df = pe_dfs[table_idx]
                        df_cols = pe_df.columns.tolist()
                        pe_df.columns = range(len(df_cols))
                        # print(pe_df)
                        remaining_df = pd.DataFrame(tables[table_idx], index=pe_df.columns).replace("", np.nan).T
                        pe_df = pd.concat([pe_df, remaining_df], axis=0).reset_index(drop=True)
                        pe_df.columns = df_cols
                        pe_dfs[table_idx] = pe_df
                    infos[-1]["product_eligibility"] = pe_dfs
    return infos

@dataclass
class ComplanTemplate:
    info: dict

    def render_table_of_contents(self):
        info = self.info
        render_template = f"""\
# Document Title: {info["Document Title"]}
## Roles Availabiity
        """
        for role, details in info["Roles Availability"].items():
            render_template += f"""
    - {role}
        - {[detail.strip() for detail in details if detail.strip() != ""]}
"""
        return render_template 
    
    def render_role_details(self):
        return f"""
{self.render_role_title(self.info)}
### the Metric Bucket Weightage of {self.info["Title"]} is {self.render_metric_bucket_weightage(self.info)}
### the Pay Curve of {self.info["Title"]} is\n{self.render_paycurve(self.info)}
{self.render_other_infos(self.info)}
### the Attainment Modifier of {self.info["Title"]} is: {self.render_attainment_modifier(self.info)}
"""
    
    def render_role_title(self, info):
        return f"## Role Title: {info['Title']}"
     
    def render_metric_bucket_weightage(self, info):
        try:
            buckets = info["Metric Bucket Weightage"][0][0][0].split("\n")
        except IndexError:
            buckets = ["No Data"]
        render_template = f"""\
"""
        metrics = []
        for idx, bucket in enumerate(buckets):
            # print(bucket)
            if "%" in bucket:
                metric_info = bucket.replace("■", "").strip()
                match_pattern = r"\s+(?=\d+\.?\d*%)\b"
                metric_info = re.split(match_pattern, metric_info)
                if len(metric_info) < 2:
                    metric_info = re.split(match_pattern, buckets[idx - 1] + " " + bucket.replace("■", "").strip()) 
                metrics.append(metric_info)
        # print(metrics)
        render_template += f"""
{pd.DataFrame(metrics, columns=["Metric Bucket", "Weightage"]).to_markdown(index=False)}

"""
        return render_template
    
    def render_paycurve(self, info):
        paycurve = pd.DataFrame(info["Pay Curve"], columns=["Attainment", "Pay Out"]).to_markdown(index=False)
        return f"""\
{paycurve}
"""
    
    def render_other_infos(self, info):
        gate_text = info.get("Gate Text", "")
        quota_cadence = info.get("Quota Cadence", "")
        unbalanced = info.get("Unbalanced", "")
        other_information = info.get("Other Information", "")
        return f"""\
### Gate Text:
the gate text of {info['Title']} is {gate_text}
### Quota Cadence:
the Quota Cadence of {info['Title']} is {quota_cadence}
### Unbalanced:
the Unbalanced of {info['Title']} is {unbalanced}
### Other Information:
the Other Information of {info['Title']} is {other_information}
"""
    
    def render_attainment_modifier(self, info):
        modifier_df = pd.DataFrame(info["Attainment Modifiers"]).dropna(thresh=2)
        spliited_modifiers = []
        for row, value in modifier_df.iterrows():
            products = value[0]
            modifiers = np.where(value[[1]].notna(), value[1], value[2])[0] if len(value) > 2 else value[1]
            for modifier in modifiers.split("\n"):
                for product in products.split("\n"):
                    spliited_modifiers.append([product, modifier])
        attainment_modifier_df = pd.DataFrame(spliited_modifiers, columns=["Product", "Modifier"]).drop_duplicates(["Product", "Modifier"])
        return f"""\
{list(attainment_modifier_df.values) if type(attainment_modifier_df) is not str else attainment_modifier_df }
"""
    
    def render_product_eligibilities(self, role_titles: list[str]):
        info = self.info["product_eligibility"]
        render_template = f"""\n
### the Product Eligibility of {role_titles} is:
"""
        for df in info:
            # print(df)
            render_template += f"""
{list(df.values)}
"""
        return render_template

def render_comp_plan_template(comp_plan):
    template = ""
    role_titles = []
    for info in comp_plan:
        content = ComplanTemplate(info)
        if "Document Title" in info:
            template += content.render_table_of_contents()
        elif "Title" in info:
            template += content.render_role_details()
            role_titles.append(info["Title"])
        else:
            template += content.render_product_eligibilities(role_titles)
            role_titles = []
        template += "===" * 60 + "\n"
    return template

def output_template_to_txt(template, file_name):
    with open(file_name, "w", encoding="utf-8") as f:
        f.write(template)

