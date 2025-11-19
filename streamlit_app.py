import streamlit as st
import os
import re
from google import genai
from google.genai.errors import APIError

# --- 1. CONFIGURATION AND INITIAL SETUP ---

# Use Streamlit's secrets for API Key management
try:
    API_KEY = os.environ.get("GEMINI_API_KEY") or st.secrets["GEMINI_API_KEY"]
except (KeyError, AttributeError):
    API_KEY = None

if not API_KEY:
    st.error("🚨 **API Key Missing!** Please set the `GEMINI_API_KEY` in your Streamlit secrets or environment variables.")
    st.stop()

# Initialize the Gemini Client
try:
    ai = genai.Client(api_key=API_KEY)
except Exception as e:
    st.error(f"Failed to initialize Gemini Client: {e}")
    st.stop()

# Set Streamlit Page Configuration (Mimicking the HTML Title)
st.set_page_config(
    page_title="AI-Powered Marketing Brief & Ads Generator",
    layout="wide"
)

# --- 2. HEADER AND UI SETUP (Mimicking index.html) ---

st.markdown(
    """
    <style>
    /* Mimic the container and font styles from index.css */
    .stApp {
        background-color: #F8F9FA; /* Light Theme subtle-bg-color */
        color: #212529; /* Light Theme text-color */
        font-family: 'Inter', sans-serif;
    }
    h1, h2, h3 {
        font-family: 'Poppins', sans-serif;
    }
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 960px; /* Max width from index.css */
        margin: 20px auto;
        padding: 25px 35px;
        background-color: #FFFFFF; /* Light Theme background-color */
        border-radius: 12px;
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.075);
    }
    .header-p {
        font-size: 1.05em;
        color: #6C757D;
    }
    /* Style for ad copy output sections (tables and pre) */
    .ad-copy-output table {
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 25px;
        font-size: 0.98em;
    }
    .ad-copy-output th, .ad-copy-output td {
        border: 1px solid #DEE2E6;
        padding: 12px 15px;
        text-align: left;
        vertical-align: top;
    }
    .ad-copy-output th {
        background-color: #E9ECEF;
        font-weight: 600;
        font-family: 'Poppins', sans-serif;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("AI-Powered Marketing Brief & Ads Generator")
st.markdown('<p class="header-p">Enter a website URL to generate a comprehensive marketing brief. Then, generate Google Ads copy based on that brief.</p>', unsafe_allow_html=True)

st.markdown("---") # Visual separator

# --- 3. INPUT FORM (Mimicking urlForm) ---

with st.form(key='marketing_form'):
    # urlInput
    url = st.text_input(
        "Website URL:",
        placeholder="https://example.com",
        help="Please include http:// or https://"
    )

    # focusServicesInput
    focus_services = st.text_area(
        "Specific Products/Services to Focus On (Optional, one per line):",
        placeholder="e.g., Eco-friendly Gadgets\nAI-Powered Analytics\nSustainable Fashion",
        height=150
    )

    # websiteOnlyCheckbox
    website_only = st.checkbox(
        "Strictly analyze website content only (disable external search for brief generation)",
        value=False
    )

    # generateAllAssetsButton
    generate_button = st.form_submit_button("Generate Ad Assets")

# --- 4. CORE GENERATION LOGIC (Mimicking index.tsx event listener) ---

def parse_ad_copy_text(raw_text: str):
    """
    Parses the raw text response from the Gemini model into a structured format.
    This function mimics the parsing and display logic in index.tsx.
    """
    output = {}
    
    # Split by section titles
    sections = re.split(r'(AD COPY VARIATION \d+.*?):|SITELINKS:|STRUCTURED SNIPPETS:|CALLOUTS:', raw_text, flags=re.IGNORECASE)
    
    # The first element is usually empty or intro text before the first title
    if len(sections) < 2:
        return {"Raw Output": raw_text}

    # Process all sections
    current_title = "Intro"
    
    # The split includes the delimiter (the title), so we process two elements at a time
    for i in range(1, len(sections)):
        section_part = sections[i].strip()
        
        if section_part.endswith(':'): # It's a title
            current_title = section_part.strip(':')
            if current_title not in output:
                output[current_title] = ""
        else: # It's content for the last found title
            output[current_title] = section_part.strip()
            # Reset title if it was a major section title (SITELINKS, etc.)
            if current_title.upper() in ["SITELINKS", "STRUCTURED SNIPPETS", "CALLOUTS"]:
                 current_title = "Temp Placeholder"
            
    return output

def format_ad_copy_table(content: str):
    """Formats Headlines and Descriptions into a Streamlit table."""
    headlines_match = re.search(r'Headlines:\s*([\s\S]*?)(Descriptions:|$)', content, re.IGNORECASE)
    descriptions_match = re.search(r'Descriptions:\s*([\s\S]*)', content, re.IGNORECASE)
    
    headlines = []
    descriptions = []

    if headlines_match and headlines_match.group(1):
        headlines = [h.strip().replace(/^- /, '') for h in headlines_match.group(1).split('\n') if h.strip().startswith('- ')]
    
    if descriptions_match and descriptions_match.group(1):
        descriptions = [d.strip().replace(/^- /, '') for d in descriptions_match.group(1).split('\n') if d.strip().startswith('- ')]
        
    max_rows = max(len(headlines), len(descriptions))
    data = []
    for i in range(max_rows):
        data.append({
            "Headlines": headlines[i] if i < len(headlines) else '–',
            "Descriptions": descriptions[i] if i < len(descriptions) else '–'
        })
        
    if data:
        st.dataframe(data, use_container_width=True, hide_index=True)
    else:
        st.write("No headlines or descriptions found for this variation.")

def format_structured_snippets(content: str):
    """Formats Structured Snippets."""
    snippet_blocks = re.split(r'\bHeader:', content, flags=re.IGNORECASE)
    for block in snippet_blocks:
        block = block.strip()
        if not block:
            continue
            
        lines = [l.strip() for l in block.split('\n')]
        if lines:
            header_text = lines[0].strip(':').strip()
            values = [v.replace('- ', '').strip() for v in lines[1:] if v.startswith('- ')]
            
            if header_text and values:
                st.subheader(header_text)
                st.markdown('\n'.join(f'* {v}' for v in values))
            elif block:
                st.code(block, language='text')

def generate_assets(url, focus_services, website_only):
    """Main function to handle Gemini calls."""
    
    # 1. URL Validation
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        from urllib.parse import urlparse
        urlparse(url) # This will raise an error for truly invalid URLs
    except ValueError:
        st.error("The entered URL is not valid. Please include http:// or https://")
        return

    # 2. Setup Prompts and Configuration (Logic ported from index.tsx)
    
    search_method = f"analyze the content found directly on the website {url}" if website_only else f"use your Google Search tool to find information about the website {url}"
    search_source = f"from the website {url}" if website_only else f"via Google Search for {url}"
    not_found_message_template = f"Could not determine {{section_name}} {search_source}."

    # Specific Services Prompt Section Logic
    specific_services_prompt_section = ""
    if focus_services:
        user_services_array = [s.strip() for s in focus_services.split('\n') if s.strip()]
        service_list_for_prompt = ''
        service_counter = 1
        
        for userService in user_services_array:
            safe_userService = userService.replace('[', '').replace(']', '')
            search_instruction = "by reviewing its content directly" if website_only else "using Google Search if needed to find relevant pages *within* that site or directly related official information"
            service_list_for_prompt += (
                f"Service/Product {service_counter} (User Specified: {safe_userService}): "
                f"[Analyze {url} ({search_instruction}) to confirm and describe \"{safe_userService}\". "
                f"If not found or detailed {search_source}, state 'User-specified service \"{safe_userService}\" could not be verified/detailed {search_source}'. "
                f"Provide concise description from website content if found.]\n"
            )
            service_counter += 1
            
        specific_services_prompt_section = f"""
Specific Services/Product Lines to Feature:
The user has expressed a specific interest in the following products/services from the website:
{focus_services}

Your task for this section:
1.  For each "User Specified" service line below, analyze the website at {url} ({search_instruction}) to gather details about it.
2.  Fill in the description for each. If a user-specified service cannot be clearly identified or detailed based on the content of {url} ({'when analyzing its content directly' if website_only else 'even with Google Search'}), explicitly state that in its description field (e.g., 'User-specified service "XYZ" could not be verified or detailed based on {url}\'s content {search_source}').
3.  After addressing all user-specified services, if there are other prominent and distinct services/product lines clearly featured on {url} that were not mentioned by the user, you MAY list and describe up to 2-3 *additional* distinct services/products, continuing the "Service/Product [number]: [description]" format (e.g., Service/Product {service_counter}: [description]).

{service_list_for_prompt}
(If applicable, continue with additional services found on {url} by you, ensuring you continue the numbering, e.g.:
Service/Product {service_counter}: [Concise description of an additional service found {search_source}]
Service/Product {service_counter + 1}: [Concise description of another additional service found {search_source}]
)
"""
    else:
        specific_services_prompt_section = f"""
Specific Services/Product Lines to Feature:
(To determine this, {search_method} to identify its key specific services or product lines. List all clearly identifiable and distinct services/products with concise descriptions based *solely* on the website's content/search findings.)
Service/Product 1: [Concise description of Service/Product 1 identified {search_source}, or '{not_found_message_template.replace("{{section_name}}", "specific service 1")}']
Service/Product 2: [Concise description of Service/Product 2 identified {search_source}, or '{not_found_message_template.replace("{{section_name}}", "specific service 2")}']
(Continue listing Service/Product 3, Service/Product 4, etc., if clearly identifiable and distinct {search_source})
"""

    # Full Marketing Brief Prompt
    marketing_brief_prompt = f"""
IMPORTANT: You MUST generate the complete marketing brief structure as outlined below. For every section, provide the requested information based on your analysis of the website {url} {'content' if website_only else 'using Google Search'}. If, after attempting to {search_method}, you cannot find specific information for a section, you MUST explicitly write a '{not_found_message_template.replace("{{section_name}}", "[section name]")}' message (e.g., '{not_found_message_template.replace("{{section_name}}", "Business Name")}') within that section. DO NOT return an empty response or omit sections. The entire structure must be present in your output. Any sections for which information cannot be found MUST contain the appropriate 'Could not determine...' phrase.

You are an expert marketing strategist. Your mission is to analyze the website at the URL "{url}" and generate a comprehensive Marketing Brief. For each section below, you will {search_method} to find the relevant information. If information for a section cannot be found after a reasonable attempt, explicitly state '{not_found_message_template.replace("{{section_name}}", "[Relevant Section Name]")}'. Address ALL sections.
{f'\\nIMPORTANT USER FOCUS: The user has specifically requested to focus on the following products/services: "{focus_services}". Please ensure your analysis, especially for "Specific Services/Product Lines to Feature", prioritizes these. For other sections, consider how these focused services might influence the overall strategy.\\n' if focus_services else ''}
Marketing Brief for Website: {url}

Business Name:
(To determine this, {search_method}. Based on your findings, state the business name. If not clearly identifiable, state '{not_found_message_template.replace("{{section_name}}", "Business Name")}')

Campaign Goal:
(To determine this, {search_method}. Explain your choice briefly based on your findings. If unclear, state '{not_found_message_template.replace("{{section_name}}", "primary campaign goal")}')

Overall Product/Service Category:
(To determine this, {search_method}. Based on your findings, describe the category. If unclear, state '{not_found_message_template.replace("{{section_name}}", "overall product/service category")}')

{specific_services_prompt_section}

Target Geographic Location(s):
(To determine this, {search_method}. Describe based on your findings. If not determinable or if the service is global/national without specific local focus, state '{not_found_message_template.replace("{{section_name}}", "specific target geographic locations")}, or service appears to be national/global'.)

Target Audience Profile(s):
(To determine this, {search_method}. Describe one primary persona. If multiple distinct personas are clearly evident from your findings for {url}, describe a second one.)
Persona 1 Name (e.g., "Tech-Savvy Startup Founder"): [Describe Demographics, Psychographics, Needs, Pain Points, What they value most, as inferred {search_source}. If not determinable, state '{not_found_message_template.replace("{{section_name}}", "Persona 1 details")}'.]
(Persona 2 Name (e.g., "Established Enterprise CTO"): [Describe Demographics, Psychographics, Needs, Pain Points, What they value most, as inferred {search_source} if a second distinct persona is evident. Otherwise, omit or state 'Second distinct persona not clearly identifiable {search_source}'.])

Primary Keywords (High Intent):
(To determine this, {search_method}. List these keywords based on your findings for {url}. If not determinable, state '{not_found_message_template.replace("{{section_name}}", "primary keywords")}')
- [Keyword 1 identified {search_source}]
- [Keyword 2 identified {search_source}]
- ...

Unique Selling Propositions (USPs) / Core Differentiators:
(To determine this, {search_method}. List 1-3 USPs based on your findings for {url}. If not determinable, state '{not_found_message_template.replace("{{section_name}}", "USPs")}')
- [USP 1 identified {search_source}]
- ...

Competitive Landscape (Optional but Recommended):
(To determine this, {search_method}. Briefly mention 1-2 competitors and a key differentiator for {url} based on your findings. If not determinable, state '{'Competitive landscape cannot be determined from website content alone for ' + url if website_only else not_found_message_template.replace("{{section_name}}", "competitive landscape")}'.)

Desired Call-to-Action (CTA):
(To determine this, {search_method}. State the main CTA based on your findings for {url}. If multiple, choose the most prominent. If not determinable, state '{not_found_message_template.replace("{{section_name}}", "primary CTA")}')

Brand Voice / Tone:
(To determine this, {search_method} and describe: "What is the brand voice or tone of the website {url} (e.g., Authoritative & Innovative, Inspiring & Exclusive, Reliable & Empathetic)?". Justify briefly based on your findings. If not determinable, state '{not_found_message_template.replace("{{section_name}}", "brand voice/tone")}')

Any Current Promotions/Offers:
(To determine this, {search_method}. If yes, describe them based on your findings. If no clear promotions are found on {url}, state 'No current promotions/offers found {search_source}'.)

Implicit Negative Intents to Avoid:
(To determine this, based on the understanding of {url} {search_source}, suggest: "What are 1-2 keyword intents or search terms that the website {url} should AVOID targeting (e.g., 'free' if it's a premium service)?". If not determinable, state '{not_found_message_template.replace("{{section_name}}", "implicit negative intents")}')
"""

    # 3. First API Call: Generate Marketing Brief
    
    st.subheader("Marketing Brief Generation")
    with st.spinner("Step 1 of 2: Generating comprehensive Marketing Brief..."):
        try:
            brief_config = {
                "model": "gemini-2.5-flash",
                "contents": marketing_brief_prompt,
            }
            if not website_only:
                brief_config["config"] = {"tools": [{"googleSearch": {}}]}
            
            brief_response = ai.models.generateContent(**brief_config)
            internal_marketing_brief = brief_response.text
            
            if not internal_marketing_brief:
                st.error("The model returned an empty response for the marketing brief.")
                return

            st.markdown("### 📝 Generated Marketing Brief")
            st.code(internal_marketing_brief, language='markdown')

        except APIError as e:
            st.error(f"Gemini API Error (Brief Generation): {e.message}")
            return
        except Exception as e:
            st.error(f"An unexpected error occurred during brief generation: {e}")
            return

    st.markdown("---")

    # 4. Second API Call: Generate Ad Copy Assets
    
    ad_copy_prompt = f"""
You are the world's unparalleled Google Ads copywriter and the pinnacle of prompt engineering.
Your mission is to generate Google Ads assets based on the following Marketing Brief.

MARKETING BRIEF:
---
{internal_marketing_brief}
---

INSTRUCTIONS:
1.  **Ad Copy Variations:**
    * Analyze the "Specific Services/Product Lines to Feature" section of the Marketing Brief. Count the number of distinct services listed (N) that have actual descriptions (not "Could not determine..." or "could not be verified/detailed"). These lines typically start with "Service/Product [number]".
    * Generate exactly N distinct "AD COPY VARIATION" blocks. If N is 0 (no services with valid descriptions found), generate one (1) general ad copy variation based on the "Overall Product/Service Category" and "Business Name" from the brief.
    * For each "AD COPY VARIATION [i]" (where [i] is 1 to N):
        * Extract the service name from the "Service/Product [i]..." line in the brief. For example, if the line is "Service/Product 1 (User Specified: Smart Thermostats): Smart Thermostats are available...", the service focus is "Smart Thermostats". If it's "Service/Product 2: Custom Software Development: We build custom software...", the focus is "Custom Software Development".
        * Clearly state which service it focuses on (e.g., "AD COPY VARIATION 1 (Service Focus: [Extracted Service Name from Brief])"). If it's a general ad copy, state "AD COPY VARIATION 1 (General Focus)".
        * **Geo-Targeting:** Analyze the "Target Geographic Location(s):" section of the Marketing Brief. If specific locations are identified (and not a "Could not determine..." message for that section), naturally incorporate these location names or location-specific phrases (e.g., "Available in [City]", "[Service] near [Location]", "Your Local [Product] Experts in [Region]") into a reasonable subset of the headlines and descriptions to enhance local relevance. Do this subtly and where appropriate. If the brief indicates a national/global service or no specific locations were determined, focus on broader appeal.
        * **You MUST include the label "Headlines:" followed by the list of headlines.** List them using a dash (-) prefix. Each headline MUST BE **STRICTLY 30 characters or less**. ABSOLUTELY NO MORE THAN 30 characters. You MUST generate **EXACTLY 25 distinct headlines**. NO MORE, NO LESS. If generating specific headlines for the service focus is challenging, you MUST provide **EXACTLY 25 relevant generic headlines** related to the business name or overall product/service category from the Marketing Brief. ALWAYS include the "Headlines:" label and ensure the list under it is NOT empty and contains 25 items.
        * **You MUST include the label "Descriptions:" followed by the list of descriptions.** List them using a dash (-) prefix. Each description MUST BE **STRICTLY 90 characters or less**. ABSOLUTELY NO MORE THAN 90 characters. You MUST generate **EXACTLY 10 distinct descriptions**. NO MORE, NO LESS. If generating specific descriptions for the service focus is challenging, you MUST provide **EXACTLY 10 relevant generic descriptions** related to the business name or overall product/service category from the Marketing Brief. ALWAYS include the "Descriptions:" label and ensure the list under it is NOT empty and contains 10 items.
    * Adhere to all Google Ads policies & best practices: hyper-relevance, keyword integration (from brief's "Primary Keywords" if available), clarity, professionalism, no gimmicks, benefit-centricity, strong CTAs (from brief's "Desired Call-to-Action" if available), USP amplification (from brief's "USPs" if available), ethical urgency/scarcity if applicable, social proof if applicable, pain point agitation & solution.
    * Ensure headline/description variety for A/B testing. Each piece must stand alone or combine effectively.

2.  **Sitelinks (4-6 variations):**
    * Based on the Marketing Brief (especially services, USPs, CTAs, and overall category, if this information was successfully determined).
    * Each Sitelink MUST adhere to the following STRICT character limits:
        * Sitelink Text: **STRICTLY 25 characters or less. ABSOLUTELY NO MORE THAN 25 characters.**
        * Description Line 1: **STRICTLY 35 characters or less. ABSOLUTELY NO MORE THAN 35 characters.**
        * Description Line 2: **STRICTLY 35 characters or less. ABSOLUTELY NO MORE THAN 35 characters.**
    * Format:
        SITELINKS:
        - Sitelink Text: [Text, adhering to 25 char limit]
          Description Line 1: [Text, adhering to 35 char limit]
          Description Line 2: [Text, adhering to 35 char limit]
        (Repeat for 4-6 variations. Ensure each part meets its specific character limit. If the brief has insufficient detail for specific sitelinks, provide generic ones based on business name/category or state 'Insufficient detail in brief for specific Sitelinks.')

3.  **Structured Snippets (2-3 distinct headers):**
    * Choose appropriate headers (e.g., Services, Types, Brands, Destinations, Models, Courses, Styles) based on the Marketing Brief's "Overall Product/Service Category" and "Specific Services/Product Lines" (if this information was successfully determined).
    * For each header, list 3-5 relevant values from the brief. Each value MUST BE **STRICTLY 25 characters or less. ABSOLUTELY NO MORE THAN 25 characters.**
    * Format:
        STRUCTURED SNIPPETS:
        Header: [Chosen Header e.g., Services]
        - [Value 1, adhering to 25 char limit]
        - [Value 2, adhering to 25 char limit]
        - [Value 3, adhering to 25 char limit]
        (Repeat for more values if applicable)
        Header: [Chosen Header e.g., Types]
        - [Value 1, adhering to 25 char limit]
        - ...
        (Repeat for 2-3 headers. If the brief has insufficient detail for specific snippets, provide generic ones or state 'Insufficient detail in brief for specific Structured Snippets.')

4.  **Callouts (4-6 variations):**
    * Highlight key benefits, USPs, or offers from the Marketing Brief (especially "USPs", "Promotions/Offers", if this information was successfully determined).
    * Each callout MUST BE **STRICTLY 25 characters or less. ABSOLUTELY NO MORE THAN 25 characters.**
    * Format:
        CALLOUTS:
        - [Callout Text 1, adhering to 25 char limit]
        - [Callout Text 2, adhering to 25 char limit]
        (Repeat for 4-6 variations. If the brief has insufficient detail for specific callouts, provide generic ones or state 'Insufficient detail in brief for specific Callouts.')

Output all sections clearly separated. Ensure absolutely no truncation of text within character limits. Maximize character usage where impactful but never exceed.
STRICTLY ADHERE TO THE "- " PREFIX FOR LISTS OF HEADLINES, DESCRIPTIONS, SITELINK VALUES, STRUCTURED SNIPPET VALUES, AND CALLOUTS. NO OTHER NUMBERS OR BULLETS.
"""

    st.subheader("Ad Copy Generation")
    with st.spinner("Step 2 of 2: Generating Google Ads Assets..."):
        try:
            adcopy_config = {
                "model": "gemini-2.5-flash",
                "contents": ad_copy_prompt,
            }
            # No need to add googleSearch tool here, as the brief has already been generated
            
            adcopy_response = ai.models.generateContent(**adcopy_config)
            raw_ad_copy_text = adcopy_response.text

            if not raw_ad_copy_text:
                st.error("The model returned an empty response for ad copies.")
                return

        except APIError as e:
            st.error(f"Gemini API Error (Ad Copy Generation): {e.message}")
            return
        except Exception as e:
            st.error(f"An unexpected error occurred during ad copy generation: {e}")
            return
            
    # 5. Display Results (Mimicking index.tsx parsing and rendering)
    st.markdown("## ✨ Generated Ad Assets")
    st.markdown('<div class="ad-copy-output">', unsafe_allow_html=True)
    
    parsed_output = parse_ad_copy_text(raw_ad_copy_text)

    for title, content in parsed_output.items():
        if title == "Raw Output":
            st.error("Could not parse ad copy content correctly, displaying raw output:")
            st.code(content, language='text')
            continue

        if not content:
            continue

        if title.upper().startswith("AD COPY VARIATION"):
            st.subheader(title)
            format_ad_copy_table(content)
        elif title.upper() == "SITELINKS":
            st.subheader(title)
            st.code(content, language='text')
        elif title.upper() == "STRUCTURED SNIPPETS":
            st.subheader(title)
            format_structured_snippets(content)
        elif title.upper() == "CALLOUTS":
            st.subheader(title)
            st.code(content, language='text')
            
    st.markdown('</div>', unsafe_allow_html=True)

# Run the generation logic if the button is clicked
if generate_button:
    generate_assets(url, focus_services, website_only)

st.markdown("---")
st.markdown("<footer><p style='text-align:center; color:#6C757D;'>Powered by Gemini API</p></footer>", unsafe_allow_html=True)
