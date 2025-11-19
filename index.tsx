/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { GoogleGenAI, GenerateContentResponse, BlockedReason, GenerateContentParameters } from '@google/genai';

// Ensure API_KEY is used as per guidelines
const apiKey = process.env.API_KEY;

const urlForm = document.getElementById('urlForm') as HTMLFormElement;
const urlInput = document.getElementById('urlInput') as HTMLInputElement;
const focusServicesInput = document.getElementById('focusServicesInput') as HTMLTextAreaElement;
const websiteOnlyCheckbox = document.getElementById('websiteOnlyCheckbox') as HTMLInputElement;
const generateAllAssetsButton = document.getElementById('generateAllAssetsButton') as HTMLButtonElement;
const themeToggleButton = document.getElementById('themeToggle') as HTMLButtonElement;


const adCopySection = document.getElementById('adCopySection') as HTMLDivElement;
const adCopyLoadingIndicator = document.getElementById('adCopyLoadingIndicator') as HTMLDivElement;
const adCopyOutputContainer = document.getElementById('adCopyOutputContainer') as HTMLDivElement;
const adCopyErrorContainer = document.getElementById('adCopyErrorContainer') as HTMLDivElement;

const initialAdCopyPlaceholder = "Ad copy variations, sitelinks, structured snippets, and callouts will appear here in a structured format.";


// Theme Toggling Logic
const sunIcon = '☀️';
const moonIcon = '🌙';

function applyTheme(theme: string) {
  if (theme === 'dark') {
    document.body.classList.add('dark-theme');
    document.body.classList.remove('light-theme');
    if (themeToggleButton) themeToggleButton.textContent = moonIcon;
    localStorage.setItem('theme', 'dark');
  } else {
    document.body.classList.add('light-theme');
    document.body.classList.remove('dark-theme');
    if (themeToggleButton) themeToggleButton.textContent = sunIcon;
    localStorage.setItem('theme', 'light');
  }
}

function toggleTheme() {
  if (document.body.classList.contains('dark-theme')) {
    applyTheme('light');
  } else {
    applyTheme('dark');
  }
}

if (themeToggleButton) {
    themeToggleButton.addEventListener('click', toggleTheme);
}

// Initialize theme
const savedTheme = localStorage.getItem('theme');
const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;

if (savedTheme) {
  applyTheme(savedTheme);
} else if (prefersDark) {
  applyTheme('dark');
} else {
  applyTheme('light'); // Default to light theme
}


if (!apiKey) {
  console.error("API_KEY environment variable not set.");
  const defaultErrorMsg = 'Configuration error: API key is missing. Please ensure the API_KEY environment variable is set.';
  
  if (adCopyErrorContainer) {
    adCopyErrorContainer.textContent = defaultErrorMsg;
    adCopyErrorContainer.style.display = 'block';
    if (adCopySection) adCopySection.style.display = 'block'; 
  } else {
      const mainContainer = document.querySelector('.container main') || document.body;
      const errorDiv = document.createElement('div');
      errorDiv.className = 'error-message'; 
      errorDiv.textContent = defaultErrorMsg;
      errorDiv.style.display = 'block';
      mainContainer.prepend(errorDiv);
  }

  if (urlInput) urlInput.disabled = true;
  if (focusServicesInput) focusServicesInput.disabled = true;
  if (websiteOnlyCheckbox) websiteOnlyCheckbox.disabled = true;
  if (generateAllAssetsButton) generateAllAssetsButton.disabled = true;
} else {
    if (adCopyOutputContainer) {
      adCopyOutputContainer.innerHTML = `<p class="placeholder-text">${initialAdCopyPlaceholder}</p>`;
    }
}

const ai = new GoogleGenAI({ apiKey: apiKey || "MISSING_API_KEY" }); 

if (urlForm) {
  urlForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!apiKey) {
      adCopyErrorContainer.textContent = 'Cannot proceed: API key is not configured.';
      adCopyErrorContainer.style.display = 'block';
      if (adCopySection) adCopySection.style.display = 'block';
      return;
    }

    const url = urlInput.value.trim();
    const focusServices = focusServicesInput.value.trim();
    const useWebsiteOnly = websiteOnlyCheckbox.checked;

    if (!url) {
      adCopyErrorContainer.textContent = 'Please enter a valid website URL.';
      adCopyErrorContainer.style.display = 'block';
      if (adCopySection) adCopySection.style.display = 'block';
      return;
    }

    try {
      new URL(url);
    } catch (_) {
      adCopyErrorContainer.textContent = 'The entered URL is not valid. Please include http:// or https://';
      adCopyErrorContainer.style.display = 'block';
      if (adCopySection) adCopySection.style.display = 'block';
      return;
    }

    generateAllAssetsButton.disabled = true;
    urlInput.disabled = true;
    focusServicesInput.disabled = true;
    websiteOnlyCheckbox.disabled = true;
    
    adCopySection.style.display = 'block'; 
    adCopyLoadingIndicator.style.display = 'flex';
    adCopyLoadingIndicator.querySelector('p')!.textContent = 'Generating all assets, this may take a moment...';
    adCopyOutputContainer.innerHTML = ''; 
    adCopyErrorContainer.style.display = 'none';

    const searchMethod = useWebsiteOnly ? 
        `analyze the content found directly on the website ${url}` : 
        `use your Google Search tool to find information about the website ${url}`;
    const searchSource = useWebsiteOnly ? `from the website ${url}` : `via Google Search for ${url}`;
    const searchSourceCaps = useWebsiteOnly ? `from Website Content for ${url}` : `via Google Search for ${url}`;
    const notFoundMessage = `Could not determine {{section_name}} ${searchSource}.`;

    let specificServicesPromptSection = `
Specific Services/Product Lines to Feature:
(To determine this, ${useWebsiteOnly ? `analyze the content of ${url} to identify its key specific services or product lines. List all clearly identifiable and distinct services/products with concise descriptions based *solely* on the website's content.` : `use your Google Search tool to identify: "What are the key specific services or product lines featured on the website ${url}?". List all clearly identifiable and distinct services/products with concise descriptions based on search findings for ${url}.`} If specific distinct services are not clear after searching ${searchSource}, describe the primary offering or state '${notFoundMessage.replace("{{section_name}}", "specific distinct services")}')
Service/Product 1: [Concise description of Service/Product 1 identified ${searchSource}, or '${notFoundMessage.replace("{{section_name}}", "specific service 1")}']
Service/Product 2: [Concise description of Service/Product 2 identified ${searchSource}, or '${notFoundMessage.replace("{{section_name}}", "specific service 2")}']
Service/Product 3: [Concise description of Service/Product 3 identified ${searchSource}, or '${notFoundMessage.replace("{{section_name}}", "specific service 3")}']
(Continue listing Service/Product 4, Service/Product 5, etc., if clearly identifiable and distinct ${searchSource})
`;

    if (focusServices) {
      const userServicesArray = focusServices.split('\n').map(s => s.trim()).filter(s => s);
      let serviceCounter = 1;
      let serviceListForPrompt = '';

      userServicesArray.forEach(userService => {
          const safeUserService = userService.replace(/[\[\]]/g, ''); 
          serviceListForPrompt += `Service/Product ${serviceCounter} (User Specified: ${safeUserService}): [Analyze ${url} ${useWebsiteOnly ? `directly` : `(using Google Search if needed to find relevant pages *within* that site or directly related official information)`} to confirm and describe "${safeUserService}". If not found or detailed ${searchSource}, state 'User-specified service "${safeUserService}" could not be verified/detailed ${searchSource}'. Provide concise description from website content if found.]\n`;
          serviceCounter++;
      });

      specificServicesPromptSection = `
Specific Services/Product Lines to Feature:
The user has expressed a specific interest in the following products/services from the website:
${focusServices}

Your task for this section:
1.  For each "User Specified" service line below, analyze the website at ${url} (${useWebsiteOnly ? `by reviewing its content directly` : `using Google Search if needed to find relevant pages *within* that site or directly related official information`}) to gather details about it.
2.  Fill in the description for each. If a user-specified service cannot be clearly identified or detailed based on the content of ${url} ${useWebsiteOnly ? `(when analyzing its content directly)` : `(even with Google Search)`}, explicitly state that in its description field (e.g., 'User-specified service "XYZ" could not be verified or detailed based on ${url}'s content ${searchSource}').
3.  After addressing all user-specified services, if there are other prominent and distinct services/product lines clearly featured on ${url} that were not mentioned by the user, you MAY list and describe up to 2-3 *additional* distinct services/products, continuing the "Service/Product [number]: [description]" format (e.g., Service/Product ${serviceCounter}: [description]).

${serviceListForPrompt}
(If applicable, continue with additional services found on ${url} by you, ensuring you continue the numbering, e.g.:
Service/Product ${serviceCounter}: [Concise description of an additional service found ${searchSource}]
Service/Product ${serviceCounter + 1}: [Concise description of another additional service found ${searchSource}]
)
`;
    }

    const marketingBriefPrompt = `
IMPORTANT: You MUST generate the complete marketing brief structure as outlined below. For every section, provide the requested information based on your analysis of the website ${url} ${useWebsiteOnly ? 'content' : 'using Google Search'}. If, after attempting to ${searchMethod}, you cannot find specific information for a section, you MUST explicitly write a '${notFoundMessage.replace("{{section_name}}", "[section name]")}' message (e.g., '${notFoundMessage.replace("{{section_name}}", "Business Name")}') within that section. DO NOT return an empty response or omit sections. The entire structure must be present in your output. Any sections for which information cannot be found MUST contain the appropriate 'Could not determine...' phrase.

You are an expert marketing strategist. Your mission is to analyze the website at the URL "${url}" and generate a comprehensive Marketing Brief. For each section below, you will ${searchMethod} to find the relevant information. If information for a section cannot be found after a reasonable attempt, explicitly state '${notFoundMessage.replace("{{section_name}}", "[Relevant Section Name]")}'. Address ALL sections.
${focusServices ? `\nIMPORTANT USER FOCUS: The user has specifically requested to focus on the following products/services: "${focusServices}". Please ensure your analysis, especially for "Specific Services/Product Lines to Feature", prioritizes these. For other sections, consider how these focused services might influence the overall strategy.\n` : ''}
Marketing Brief for Website: ${url}

Business Name:
(To determine this, ${useWebsiteOnly ? `analyze the content of ${url} (e.g., footer, about page, titles) to find the business name.` : `use your Google Search tool to find the answer to: "What is the business name of the website ${url}?".`} Based on your findings, state the business name. If not clearly identifiable, state '${notFoundMessage.replace("{{section_name}}", "Business Name")}')

Campaign Goal:
(To determine this, ${useWebsiteOnly ? `analyze ${url}'s content and offerings to infer its most likely primary campaign goal (e.g., Generate Leads, Drive Online Sales, Increase Brand Awareness, Get App Downloads).` : `use your Google Search tool to find information that helps answer: "What is the most likely primary campaign goal for the website ${url}, based on its content and offerings (e.g., Generate Leads, Drive Online Sales, Increase Brand Awareness, Get App Downloads)?".`} Explain your choice briefly based on your findings. If unclear, state '${notFoundMessage.replace("{{section_name}}", "primary campaign goal")}')

Overall Product/Service Category:
(To determine this, ${useWebsiteOnly ? `analyze the main content of ${url} to identify the main category of products or services offered (e.g., SaaS for Project Management, Luxury Travel Experiences, Residential HVAC Services).` : `use your Google Search tool to find the answer to: "What is the main category of products or services offered by the website ${url} (e.g., SaaS for Project Management, Luxury Travel Experiences, Residential HVAC Services)?".`} Based on your findings, describe the category. If unclear, state '${notFoundMessage.replace("{{section_name}}", "overall product/service category")}')

${specificServicesPromptSection}

Target Geographic Location(s):
(To determine this, ${useWebsiteOnly ? `analyze ${url} for mentions of specific service areas, contact pages, or regional information.` : `use your Google Search tool to identify: "What are the primary target geographic locations or service areas for the website ${url} (e.g., specific cities, regions, or if it's a national/international service)?".`} Describe based on your findings. If not determinable or if the service is global/national without specific local focus, state '${notFoundMessage.replace("{{section_name}}", "specific target geographic locations")}, or service appears to be national/global'.)

Target Audience Profile(s):
(To determine this, ${useWebsiteOnly ? `infer from the language, imagery, and offerings on ${url} who the primary target audience is.` : `use your Google Search tool to infer: "Who is the primary target audience for the website ${url}, based on its content, products/services, and overall presentation?".`} Describe one primary persona. If multiple distinct personas are clearly evident from your findings for ${url}, describe a second one.)
Persona 1 Name (e.g., "Tech-Savvy Startup Founder"): [Describe Demographics, Psychographics, Needs, Pain Points, What they value most, as inferred ${searchSource}. If not determinable, state '${notFoundMessage.replace("{{section_name}}", "Persona 1 details")}'.]
(Persona 2 Name (e.g., "Established Enterprise CTO"): [Describe Demographics, Psychographics, Needs, Pain Points, What they value most, as inferred ${searchSource} if a second distinct persona is evident. Otherwise, omit or state 'Second distinct persona not clearly identifiable ${searchSource}'.])

Primary Keywords (High Intent):
(To determine this, ${useWebsiteOnly ? `based on the services, products, and overall content of ${url}, identify 5-8 high-intent primary keywords someone would use to find these offerings.` : `use your Google Search tool to identify: "What are 5-8 high-intent primary keywords someone would use to find the products/services offered on ${url}?".`} List these keywords based on your findings for ${url}. If not determinable, state '${notFoundMessage.replace("{{section_name}}", "primary keywords")}')
- [Keyword 1 identified ${searchSource}]
- [Keyword 2 identified ${searchSource}]
- ...

Unique Selling Propositions (USPs) / Core Differentiators:
(To determine this, ${useWebsiteOnly ? `analyze ${url} to identify what makes its offerings unique or different from potential competitors, focusing on explicitly stated benefits or features.` : `use your Google Search tool to find: "What makes the offerings on ${url} unique or different from competitors?".`} List 1-3 USPs based on your findings for ${url}. If not determinable, state '${notFoundMessage.replace("{{section_name}}", "USPs")}')
- [USP 1 identified ${searchSource}]
- ...

Competitive Landscape (Optional but Recommended):
(To determine this, ${useWebsiteOnly ? `if the website ${url} explicitly mentions competitors or comparative advantages, summarize them. Otherwise, acknowledge that determining external competitors is outside the scope of direct website analysis.` : `use your Google Search tool to identify: "Who are the main competitors for the website ${url}, and how do their offerings compare?".`} Briefly mention 1-2 competitors and a key differentiator for ${url} based on your findings. If not determinable, state '${useWebsiteOnly ? `Competitive landscape cannot be determined from website content alone for ${url}` : notFoundMessage.replace("{{section_name}}", "competitive landscape")}'.)

Desired Call-to-Action (CTA):
(To determine this, ${useWebsiteOnly ? `identify the primary call-to-action (e.g., 'Contact Us', 'Shop Now', 'Request a Demo') prominently featured on ${url}.` : `use your Google Search tool to find: "What is the primary call-to-action promoted on the website ${url}?".`} State the main CTA based on your findings for ${url}. If multiple, choose the most prominent. If not determinable, state '${notFoundMessage.replace("{{section_name}}", "primary CTA")}')

Brand Voice / Tone:
(To determine this, analyze the language, style, and imagery on ${url} ${useWebsiteOnly ? `directly` : `through Google Search results`} and describe: "What is the brand voice or tone of the website ${url} (e.g., Authoritative & Innovative, Inspiring & Exclusive, Reliable & Empathetic)?". Justify briefly based on your findings. If not determinable, state '${notFoundMessage.replace("{{section_name}}", "brand voice/tone")}')

Any Current Promotions/Offers:
(To determine this, ${useWebsiteOnly ? `look for any current promotions or special offers mentioned directly on ${url}.` : `use your Google Search tool to find: "Are there any current promotions or special offers mentioned on the website ${url}?".`} If yes, describe them based on your findings. If no clear promotions are found on ${url}, state 'No current promotions/offers found ${searchSource}'.)

Implicit Negative Intents to Avoid:
(To determine this, based on the understanding of ${url} ${useWebsiteOnly ? `from its content` : `from Google Search`}, suggest: "What are 1-2 keyword intents or search terms that the website ${url} should AVOID targeting (e.g., 'free' if it's a premium service)?". If not determinable, state '${notFoundMessage.replace("{{section_name}}", "implicit negative intents")}')
`;

    let internalMarketingBrief = '';

    try {
      const briefGenerationConfig: GenerateContentParameters = {
        model: "gemini-2.5-flash",
        contents: marketingBriefPrompt,
      };

      if (!useWebsiteOnly) {
        briefGenerationConfig.config = {
          tools: [{googleSearch: {}}],
        };
      }
      
      const briefResult: GenerateContentResponse = await ai.models.generateContent(briefGenerationConfig);

      internalMarketingBrief = briefResult.text;
      
      if (!internalMarketingBrief || internalMarketingBrief.trim() === '') {
        let detailedErrorMessage = 'Could not generate the internal marketing brief. The model returned an empty response.';
        let consoleLogSuffix = "";

        if (briefResult.promptFeedback) {
            if (briefResult.promptFeedback.blockReason && briefResult.promptFeedback.blockReason !== BlockedReason.BLOCKED_REASON_UNSPECIFIED) {
                detailedErrorMessage = `Marketing brief generation potentially blocked. Reason: ${briefResult.promptFeedback.blockReason}.`;
                consoleLogSuffix += ` BlockReason: ${briefResult.promptFeedback.blockReason}.`;
            }
            if (briefResult.promptFeedback.safetyRatings && briefResult.promptFeedback.safetyRatings.length > 0) {
                consoleLogSuffix += ` SafetyRatings: ${JSON.stringify(briefResult.promptFeedback.safetyRatings)}.`;
            }
        }
        
        if (briefResult.candidates && briefResult.candidates.length > 0) {
            const firstCandidate = briefResult.candidates[0];
            if (firstCandidate.finishReason && firstCandidate.finishReason !== 'STOP') {
                const reasonMsg = `Generation stopped unexpectedly. Reason: ${firstCandidate.finishReason}.`;
                if (detailedErrorMessage.includes('model returned an empty response')) { 
                    detailedErrorMessage = reasonMsg;
                } else if (!detailedErrorMessage.includes(firstCandidate.finishReason)) { 
                    detailedErrorMessage += ` (Candidate finish reason: ${firstCandidate.finishReason})`;
                }
                consoleLogSuffix += ` FinishReason: ${firstCandidate.finishReason}.`;
            }
        }
        
        console.error(`Internal marketing brief generation returned empty. UI Message: "${detailedErrorMessage}". Diagnostic Info: ${consoleLogSuffix} Full response object:`, briefResult);
        adCopyErrorContainer.textContent = detailedErrorMessage;
        adCopyErrorContainer.style.display = 'block';
        adCopyLoadingIndicator.style.display = 'none';
        generateAllAssetsButton.disabled = false;
        urlInput.disabled = false;
        focusServicesInput.disabled = false;
        websiteOnlyCheckbox.disabled = false;
        return; 
      }

      const adCopyPrompt = `
You are the world's unparalleled Google Ads copywriter and the pinnacle of prompt engineering.
Your mission is to generate Google Ads assets based on the following Marketing Brief.

MARKETING BRIEF:
---
${internalMarketingBrief}
---

INSTRUCTIONS:
1.  **Ad Copy Variations:**
    *   Analyze the "Specific Services/Product Lines to Feature" section of the Marketing Brief. Count the number of distinct services listed (N) that have actual descriptions (not "Could not determine..." or "could not be verified/detailed"). These lines typically start with "Service/Product [number]".
    *   Generate exactly N distinct "AD COPY VARIATION" blocks. If N is 0 (no services with valid descriptions found), generate one (1) general ad copy variation based on the "Overall Product/Service Category" and "Business Name" from the brief.
    *   For each "AD COPY VARIATION [i]" (where [i] is 1 to N):
        *   Extract the service name from the "Service/Product [i]..." line in the brief. For example, if the line is "Service/Product 1 (User Specified: Smart Thermostats): Smart Thermostats are available...", the service focus is "Smart Thermostats". If it's "Service/Product 2: Custom Software Development: We build custom software...", the focus is "Custom Software Development".
        *   Clearly state which service it focuses on (e.g., "AD COPY VARIATION 1 (Service Focus: [Extracted Service Name from Brief])"). If it's a general ad copy, state "AD COPY VARIATION 1 (General Focus)".
        *   **Geo-Targeting:** Analyze the "Target Geographic Location(s):" section of the Marketing Brief. If specific locations are identified (and not a "Could not determine..." message for that section), naturally incorporate these location names or location-specific phrases (e.g., "Available in [City]", "[Service] near [Location]", "Your Local [Product] Experts in [Region]") into a reasonable subset of the headlines and descriptions to enhance local relevance. Do this subtly and where appropriate. If the brief indicates a national/global service or no specific locations were determined, focus on broader appeal.
        *   **You MUST include the label "Headlines:" followed by the list of headlines.** List them using a dash (-) prefix. Each headline MUST BE **STRICTLY 30 characters or less**. ABSOLUTELY NO MORE THAN 30 characters. You MUST generate **EXACTLY 25 distinct headlines**. NO MORE, NO LESS. If generating specific headlines for the service focus is challenging, you MUST provide **EXACTLY 25 relevant generic headlines** related to the business name or overall product/service category from the Marketing Brief. ALWAYS include the "Headlines:" label and ensure the list under it is NOT empty and contains 25 items.
        *   **You MUST include the label "Descriptions:" followed by the list of descriptions.** List them using a dash (-) prefix. Each description MUST BE **STRICTLY 90 characters or less**. ABSOLUTELY NO MORE THAN 90 characters. You MUST generate **EXACTLY 10 distinct descriptions**. NO MORE, NO LESS. If generating specific descriptions for the service focus is challenging, you MUST provide **EXACTLY 10 relevant generic descriptions** related to the business name or overall product/service category from the Marketing Brief. ALWAYS include the "Descriptions:" label and ensure the list under it is NOT empty and contains 10 items.
    *   Adhere to all Google Ads policies & best practices: hyper-relevance, keyword integration (from brief's "Primary Keywords" if available), clarity, professionalism, no gimmicks, benefit-centricity, strong CTAs (from brief's "Desired Call-to-Action" if available), USP amplification (from brief's "USPs" if available), ethical urgency/scarcity if applicable, social proof if applicable, pain point agitation & solution.
    *   Ensure headline/description variety for A/B testing. Each piece must stand alone or combine effectively.

2.  **Sitelinks (4-6 variations):**
    *   Based on the Marketing Brief (especially services, USPs, CTAs, and overall category, if this information was successfully determined).
    *   Each Sitelink MUST adhere to the following STRICT character limits:
        *   Sitelink Text: **STRICTLY 25 characters or less. ABSOLUTELY NO MORE THAN 25 characters.**
        *   Description Line 1: **STRICTLY 35 characters or less. ABSOLUTELY NO MORE THAN 35 characters.**
        *   Description Line 2: **STRICTLY 35 characters or less. ABSOLUTELY NO MORE THAN 35 characters.**
    *   Format:
        SITELINKS:
        - Sitelink Text: [Text, adhering to 25 char limit]
          Description Line 1: [Text, adhering to 35 char limit]
          Description Line 2: [Text, adhering to 35 char limit]
        (Repeat for 4-6 variations. Ensure each part meets its specific character limit. If the brief has insufficient detail for specific sitelinks, provide generic ones based on business name/category or state 'Insufficient detail in brief for specific Sitelinks.')

3.  **Structured Snippets (2-3 distinct headers):**
    *   Choose appropriate headers (e.g., Services, Types, Brands, Destinations, Models, Courses, Styles) based on the Marketing Brief's "Overall Product/Service Category" and "Specific Services/Product Lines" (if this information was successfully determined).
    *   For each header, list 3-5 relevant values from the brief. Each value MUST BE **STRICTLY 25 characters or less. ABSOLUTELY NO MORE THAN 25 characters.**
    *   Format:
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
    *   Highlight key benefits, USPs, or offers from the Marketing Brief (especially "USPs", "Promotions/Offers", if this information was successfully determined).
    *   Each callout MUST BE **STRICTLY 25 characters or less. ABSOLUTELY NO MORE THAN 25 characters.**
    *   Format:
        CALLOUTS:
        - [Callout Text 1, adhering to 25 char limit]
        - [Callout Text 2, adhering to 25 char limit]
        (Repeat for 4-6 variations. If the brief has insufficient detail for specific callouts, provide generic ones or state 'Insufficient detail in brief for specific Callouts.')

Output all sections clearly separated. Ensure absolutely no truncation of text within character limits. Maximize character usage where impactful but never exceed.
STRICTLY ADHERE TO THE "- " PREFIX FOR LISTS OF HEADLINES, DESCRIPTIONS, SITELINK VALUES, STRUCTURED SNIPPET VALUES, AND CALLOUTS. NO OTHER NUMBERS OR BULLETS.
`;
      const adCopyResult: GenerateContentResponse = await ai.models.generateContent({
        model: "gemini-2.5-flash",
        contents: adCopyPrompt,
      });
      const rawAdCopyText = adCopyResult.text;
      console.log('Raw AI Response for Ad Copies:', rawAdCopyText);

      if (rawAdCopyText) {
        adCopyOutputContainer.innerHTML = ''; 

        const sections = rawAdCopyText.split(/AD COPY VARIATION \d+|SITELINKS:|STRUCTURED SNIPPETS:|CALLOUTS:/gi);
        const titles = rawAdCopyText.match(/AD COPY VARIATION \d+ \(Service Focus: [^\)]+\)|AD COPY VARIATION \d+ \(General Focus\)|AD COPY VARIATION \d+|SITELINKS:|STRUCTURED SNIPPETS:|CALLOUTS:/gi) || [];

        let contentIndex = 0;
        if (rawAdCopyText.toUpperCase().startsWith("AD COPY VARIATION") || rawAdCopyText.toUpperCase().startsWith("SITELINKS:") || rawAdCopyText.toUpperCase().startsWith("STRUCTURED SNIPPETS:") || rawAdCopyText.toUpperCase().startsWith("CALLOUTS:")) {
            contentIndex = 1; 
        } else {
            if(sections.length > 0 && sections[0].trim() !== "") {
                const introPara = document.createElement('p');
                introPara.textContent = sections[0].trim();
                adCopyOutputContainer.appendChild(introPara);
            }
            contentIndex = 1; 
        }
         if (titles.length === 0 && sections.length > 0 && sections[0].trim() !== "") {
            const pre = document.createElement('pre');
            pre.textContent = sections[0].trim();
            adCopyOutputContainer.appendChild(pre);
        }


        titles.forEach((title, index) => {
          const currentSectionContent = sections[index + contentIndex]?.trim() || "";

          console.log('Processing Section - Title:', title, 'Content Snippet:', currentSectionContent.substring(0,100) + "...");

          const sectionElementContainer = document.createElement('div');
          sectionElementContainer.className = 'output-section-item'; 

          const heading = document.createElement('h3');
          heading.textContent = title.trim().replace(/:$/, ''); 
          sectionElementContainer.appendChild(heading);

          if (title.toUpperCase().startsWith("AD COPY VARIATION")) {
            const headlinesMatch = currentSectionContent.match(/Headlines:\s*([\s\S]*?)(Descriptions:|$)/i);
            const descriptionsMatch = currentSectionContent.match(/Descriptions:\s*([\s\S]*)/i);

            const headlinesText = headlinesMatch && headlinesMatch[1] ? headlinesMatch[1].trim() : "";
            const descriptionsText = descriptionsMatch && descriptionsMatch[1] ? descriptionsMatch[1].trim() : "";

            const headlines = headlinesText.split('\n').map(h => h.replace(/^- /, '').trim()).filter(h => h);
            const descriptions = descriptionsText.split('\n').map(d => d.replace(/^- /, '').trim()).filter(d => d);

            if (headlines.length > 0 || descriptions.length > 0) {
              const table = document.createElement('table');
              const thead = table.createTHead();
              const headerRow = thead.insertRow();
              const th1 = document.createElement('th');
              th1.textContent = 'Headlines';
              headerRow.appendChild(th1);
              const th2 = document.createElement('th');
              th2.textContent = 'Descriptions';
              headerRow.appendChild(th2);
              const tbody = table.createTBody();
              const maxRows = Math.max(headlines.length, descriptions.length);
              for (let i = 0; i < maxRows; i++) {
                const row = tbody.insertRow();
                row.insertCell().textContent = headlines[i] || '';
                row.insertCell().textContent = descriptions[i] || '';
              }
              sectionElementContainer.appendChild(table);
            } else {
              const noDataTablePara = document.createElement('p');
              noDataTablePara.textContent = 'No headlines or descriptions found for this variation.';
              sectionElementContainer.appendChild(noDataTablePara);
            }
          } else if (title.toUpperCase().startsWith("SITELINKS:") || title.toUpperCase().startsWith("CALLOUTS:")) {
            if (currentSectionContent) {
              const pre = document.createElement('pre');
              pre.textContent = currentSectionContent; 
              sectionElementContainer.appendChild(pre);
            } else {
              const p = document.createElement('p');
              p.textContent = "No content for this section.";
              sectionElementContainer.appendChild(p);
            }
          } else if (title.toUpperCase().startsWith("STRUCTURED SNIPPETS:")) {
            if (currentSectionContent) {
              const snippetBlocks = currentSectionContent.split(/\bHeader:/gi).map(s => s.trim()).filter(s => s);

              if (snippetBlocks.length > 0) {
                snippetBlocks.forEach(block => {
                  const lines = block.split('\n').map(l => l.trim());
                  if (lines.length > 0) {
                    const headerText = lines[0].replace(/:$/, '').trim(); 
                    const values = lines.slice(1).filter(v => v.startsWith("- ")).map(v => v.trim());

                    if (headerText && values.length > 0) {
                      const subHeading = document.createElement('h4');
                      subHeading.textContent = headerText;
                      subHeading.style.marginTop = "0.8em";
                      subHeading.style.marginBottom = "0.4em";
                      subHeading.style.fontSize = "1.15rem";
                      subHeading.style.fontFamily = "var(--font-family-headings)";
                      sectionElementContainer.appendChild(subHeading);

                      const ul = document.createElement('ul');
                      ul.style.listStyleType = "disc";
                      ul.style.paddingLeft = "20px"; 
                      ul.style.marginTop = "0.3em";
                      values.forEach(value => {
                        const li = document.createElement('li');
                        li.textContent = value.startsWith("- ") ? value.substring(2).trim() : value.trim();
                        li.style.marginBottom = "0.2em";
                        ul.appendChild(li);
                      });
                      sectionElementContainer.appendChild(ul);
                    } else if (block) { 
                      const pre = document.createElement('pre');
                      pre.textContent = `Header: ${block}`; 
                      sectionElementContainer.appendChild(pre);
                    }
                  }
                });
              } else if (currentSectionContent) { 
                const pre = document.createElement('pre');
                pre.textContent = currentSectionContent;
                sectionElementContainer.appendChild(pre);
              }
            } else {
              const p = document.createElement('p');
              p.textContent = "No content for this section.";
              sectionElementContainer.appendChild(p);
            }
          }
          adCopyOutputContainer.appendChild(sectionElementContainer);
        });

         if (adCopyOutputContainer.innerHTML.trim() === '') {
             adCopyOutputContainer.innerHTML = `<p>Could not parse ad copy content correctly, but received a response. Displaying raw output:</p><pre>${rawAdCopyText}</pre>`;
         }
      } else {
        adCopyOutputContainer.innerHTML = `<p class="placeholder-text">The model returned an empty response for ad copies.</p>`;
        adCopyErrorContainer.textContent = 'The model returned an empty response for ad copies.';
        adCopyErrorContainer.style.display = 'block';
      }

    } catch (error: any) {
      console.error("Error during generation process:", error);
      let errorMessage = 'An unexpected error occurred.';
      if (error.message) {
          errorMessage = `Error: ${error.message}`;
      } else if (typeof error === 'string') {
          errorMessage = error;
      } else if (error.toString) {
          errorMessage = error.toString();
      }
      adCopyErrorContainer.textContent = errorMessage;
      adCopyErrorContainer.style.display = 'block';
      adCopyOutputContainer.innerHTML = `<p class="placeholder-text">${initialAdCopyPlaceholder}</p>`; 
    } finally {
      adCopyLoadingIndicator.style.display = 'none';
      generateAllAssetsButton.disabled = false;
      urlInput.disabled = false;
      focusServicesInput.disabled = false;
      websiteOnlyCheckbox.disabled = false;
    }
  });
}
