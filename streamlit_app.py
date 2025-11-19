import streamlit as st
import os
import re
from google import genai
from google.genai.errors import APIError
from urllib.parse import urlparse # Used for URL validation

# --- 1. CONFIGURATION AND INITIAL SETUP ---

# Use Streamlit's secrets for API Key management
# IMPORTANT: Ensure GEMINI_API_KEY is set in your Streamlit secrets.toml or environment variables
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

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="AI-Powered Marketing Brief & Ads Generator",
    layout="wide"
)

# --- 2. HELPER FUNCTIONS ---

def parse_ad_copy_text(raw_text: str):
    """
    Parses the raw text response from the Gemini model into a structured dictionary.
    """
    output = {}
    
    # Use a flexible regex to split by all major section titles
    sections = re.split(r'(AD COPY VARIATION \d+.*?):|SITELINKS:|STRUCTURED SNIPPETS:|CALLOUTS:', raw_text, flags=re.IGNORECASE)
    
    # Process sections, skipping the first element which is usually pre-text
    current_title = "Intro"
    for i in range(len(sections)):
        section_part = sections[i].strip()
        
        if not section_part:
            continue
            
        # Check if this part is a title (ends with colon or is a known major title)
        if section_part.upper().startswith(("AD COPY VARIATION", "SITELINKS", "STRUCTURED SNIPPETS", "CALLOUTS")):
            current_title = section_part.strip(':').strip()
            output[current_title] = ""
        elif current_title in output and output[current_title] == "":
            # Append content to the current title, ensuring not to overwrite
            output[current_title] = section_part
        elif i == 0:
             # Handle possible intro text before the first formal section
             output["Intro"] = section_part
            
    return output

def format_ad_copy_table(content: str):
    """Formats Headlines and Descriptions into a Streamlit table."""
    headlines_match = re.search(r'Headlines:\s*([\s\S]*?)(Descriptions:|$)', content, re.IGNORECASE)
    descriptions_match = re.search(r'Descriptions:\s*([\s\S]*)', content, re.IGNORECASE)
    
    headlines = []
    descriptions = []

    if headlines_match and headlines_match.group(1):
        # Using re.sub() for regex replacement to remove the '- ' prefix
        headlines = [re.sub(r'^- ', '', h.strip()) for h in headlines_match.group(1).split('\n') if h.strip().startswith('- ')]
    
    if descriptions_match and descriptions_match.group(1):
        # Using re.sub() for regex replacement to remove the '- ' prefix
        descriptions = [re.sub(r'^- ', '', d.strip()) for d in descriptions_match.group(1).split('\n') if d.strip().startswith('- ')]
        
    max_rows = max(len(headlines), len(descriptions))
    data = []
    for i in range(max_rows):
        data.append({
            "Headlines (Max 30 Chars)": headlines[i] if i < len(headlines) else '–',
            "Descriptions (Max 90 Chars)": descriptions[i] if i < len(descriptions) else '–'
        })
        
    if data:
        st.dataframe(data, use_container_width=True, hide_index=True)
    else:
        st.write("No headlines or descriptions found for this variation.")

def format_structured_snippets(content: str):
    """Formats Structured Snippets (Header: Value lists)."""
    snippet_blocks = re.split(r'\bHeader:', content, flags=re.IGNORECASE)
    for block in snippet_blocks:
        block = block.strip()
        if not block:
            continue
            
        lines = [l.strip() for l in block.split('\n')]
        if lines:
            header_text = lines[0].strip(':').strip()
            # Filter and clean values starting with '- '
            values = [v.replace('- ', '').strip() for v in lines[1:] if v.startswith('- ')]
            
            if header_text and values:
                st.markdown(f"**{header_text}**")
                st.markdown('\n'.join(f'* {v}' for v in values))
            elif block:
                st.code(block, language='text')

# --- 3. UI DISPLAY ---

# Inject basic CSS styles for a cleaner look
st.markdown(
    """
    <style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 960px;
        margin: 20px auto;
        padding: 25px 35px;
        background-color: #FFFFFF;
        border-radius: 12px;
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.075);
    }
    .header-p {
        font-size: 1.05em;
        color: #6C757D;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("AI-Powered Marketing Brief & Ads Generator")
st.markdown('<p class="header-p">Enter a website URL to generate a comprehensive marketing brief. Then, generate Google Ads copy based on that brief.</p>', unsafe_allow_html=True)

st.markdown("---") # Visual separator

# --- 4. INPUT FORM ---

with st.form(key='marketing_form'):
    url = st.text_input(
        "Website URL:",
        placeholder="https://example.com",
        help="Please include http:// or https://"
    )

    focus_services = st.text_area(
        "Specific Products/Services to Focus On (Optional, one per line):",
        placeholder="e.g., Eco-friendly Gadgets\nAI-Powered Analytics\nSustainable Fashion",
        height=150
    )

    website_only = st.checkbox(
        "Strictly analyze website content only (disable external search for brief generation)",
        value=False
    )

    generate_button = st.form_submit_button("Generate Ad Assets")

# --- 5. CORE GENERATION LOGIC ---

def generate_assets(url, focus_services, website_only):
    """Handles the two-step Gemini API calls."""
    
    # 1. URL Validation
    try:
        # Prepend https:// if no scheme is provided, for robust parsing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        urlparse(url) # This will raise an error for truly invalid URLs
    except ValueError:
        st.error("❌ **Invalid URL:** The entered URL is not valid. Please ensure it includes http:// or https:// and is correctly formatted.")
        return

    # 2. Setup Prompts and Configuration
    
    search_method = f"analyze the content found directly on the website {url}" if website_only else f"use your Google Search tool to find information about the website {url}"
    search_source = f"from the website {url}" if website_only else f"via Google Search for {url}"
    not_found_message_template = f"Could not determine {{section_name}} {search_source}."

    # Logic for Specific Services Section (Highly verbose to ensure model adheres to constraints)
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
    
    # Full Marketing Brief Prompt (Highly verbose to ensure model adheres to constraints)
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
(To determine this, {search_method}. Describe the category. If unclear, state '{not_found_message_template.replace("{{section_name}}", "overall product/service category")}')

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
    brief_placeholder = st.empty()
    brief_placeholder.info("Step 1 of 2: Generating comprehensive Marketing Brief...")
    
    try:
        brief_config = {
            "model": "gemini-2.5-flash",
            "contents": marketing_brief_prompt,
        }
        if not website_only:
            brief_config["config"] = {"tools": [{"googleSearch": {}}]}
        
        # Corrected to use snake_case generate_content
        brief_response = ai.models.generate_content(**brief_config)
        internal_marketing_brief = brief_response.text
        
        if not internal_marketing_brief:
            brief_placeholder.error("The model returned an empty response for the marketing brief.")
            return

        brief_placeholder.empty()
        st.markdown("### 📝 Generated Marketing Brief")
        st.code(internal_marketing_brief, language='markdown')

    except APIError as e:
        brief_placeholder.error(f"❌ Gemini API Error (Brief Generation): {e.message}")
        return
    except Exception as e:
        brief_placeholder.error(f"❌ An unexpected error occurred during brief generation: {e}")
        return

    st.markdown("---")

    # 4. Second API Call: Generate Ad Copy Assets
    
    # SIMPLIFIED AD COPY PROMPT
    ad_copy_prompt = f"""
You are the world's unparalleled Google Ads copywriter and the pinnacle of prompt engineering.
Your mission is to generate Google Ads assets based on the following Marketing Brief.

MARKETING BRIEF:
---
{internal_marketing_brief}
---

INSTRUCTIONS (SIMPLIFIED TO REDUCE OUTPUT VOLUME):
1.  **Ad Copy Variations:**
    * Analyze the "Specific Services/Product Lines to Feature" section of the Marketing Brief. Count the number of distinct services listed (N) that have actual descriptions (not "Could not determine..." or "could not be verified/detailed"). These lines typically start with "Service/Product [number]".
    * Generate exactly N distinct "AD COPY VARIATION" blocks. If N is 0 (no services with valid descriptions found), generate one (1) general ad copy variation.
    * For each "AD COPY VARIATION [i]":
        * Clearly state the service focus (e.g., "AD COPY VARIATION 1 (Service Focus: [Extracted Service Name from Brief])").
        * **Headlines:** You MUST generate **EXACTLY 12 distinct headlines**. Each headline MUST BE **STRICTLY 30 characters or less**.
        * **Descriptions:** You MUST generate **EXACTLY 4 distinct descriptions**. Each description MUST BE **STRICTLY 90 characters or less**.
        * **Formatting:** You MUST include the labels "Headlines:" and "Descriptions:", and list items using the dash prefix (`- `).

2.  **Sitelinks (3 variations):**
    * Generate **EXACTLY 3 Sitelink variations**.
    * Each Sitelink MUST adhere to the following STRICT character limits: Sitelink Text: **STRICTLY 25 characters or less**. Description Line 1: **STRICTLY 35 characters or less**. Description Line 2: **STRICTLY 35 characters or less**.
    * Format: Use the multiline format shown in the previous prompt.

3.  **Structured Snippets (2 distinct headers):**
    * Choose 2 appropriate headers (e.g., Services, Types).
    * For each header, list 3-5 relevant values. Each value MUST BE **STRICTLY 25 characters or less**.

4.  **Callouts (3 variations):**
    * Generate **EXACTLY 3 Callout variations**.
    * Each callout MUST BE **STRICTLY 25 characters or less**.
    * Format: List using the dash prefix (`- `).

Output all sections clearly separated. Adhere STRICTLY to the new reduced character and quantity limits.
"""

    st.subheader("Ad Copy Generation")
    adcopy_placeholder = st.empty()
    adcopy_placeholder.info("Step 2 of 2: Generating Google Ads Assets...")

    try:
        adcopy_config = {
            "model": "gemini-2.5-flash",
            "contents": ad_copy_prompt,
        }
        
        # Corrected to use snake_case generate_content
        adcopy_response = ai.models.generate_content(**adcopy_config)
        raw_ad_copy_text = adcopy_response.text

        if not raw_ad_copy_text:
            adcopy_placeholder.error("The model returned an empty response for ad copies.")
            return

    except APIError as e:
        adcopy_placeholder.error(f"❌ Gemini API Error (Ad Copy Generation): {e.message}")
        return
    except Exception as e:
        adcopy_placeholder.error(f"❌ An unexpected error occurred during ad copy generation: {e}")
        return
            
    # 5. Display Results
    adcopy_placeholder.empty()
    st.markdown("## ✨ Generated Ad Assets")
    
    parsed_output = parse_ad_copy_text(raw_ad_copy_text)

    for title, content in parsed_output.items():
        if title == "Intro":
            continue

        if not content:
            continue

        st.markdown(f"### {title.strip()}")

        if title.upper().startswith("AD COPY VARIATION"):
            format_ad_copy_table(content)
        elif title.upper() == "STRUCTURED SNIPPETS":
            format_structured_snippets(content)
        else: # Sitelinks and Callouts
            # Display raw text for these sections as they are already structured lists
            st.code(content, language='text')

# --- 6. EXECUTION ---
if generate_button:
    generate_assets(url, focus_services, website_only)

st.markdown("---")
st.markdown("<footer><p style='text-align:center; color:#6C757D;'>Powered by Gemini API</p></footer>", unsafe_allow_html=True)
