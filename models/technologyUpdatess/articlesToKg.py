import re

data = """
Title: Congrats to the GitHub Copilot 1-Day Build Challenge Winners!, URL: https://dev.to/devteam/congrats-to-the-github-copilot-1-day-build-challenge-winners-4iok
Title: Exploring OpenAI Operator, URL: https://dev.to/burcs/exploring-openai-operator-your-ai-powered-browser-assistant-3dj2
Title: You don't know it, but your open-source might be worth millions of dollars 🤑, URL: https://dev.to/nevodavid/you-dont-know-it-but-your-open-source-might-be-worth-millions-of-dollars-47c
Title: Introducing Jolt: AI Codegen and Chat for 100K to Multi-Million Line Codebases, URL: https://dev.to/yev_yev_yev/introducing-jolt-ai-codegen-and-chat-for-100k-to-multi-million-line-codebases-1764
Title: Tester in 2025: Can Artificial Intelligence Replace Us?, URL: https://dev.to/leo_scott_357f10236fabe00/tester-in-2025-can-artificial-intelligence-replace-us-7jd
Title: How ContentCraft Repurposes Your Blog Posts with AI, URL: https://dev.to/ifihan/how-contentcraft-repurposes-your-blog-posts-with-ai-573g
Title: How to Train AI Models for Real-World Applications?, URL: https://dev.to/julioherreravelutini/how-to-train-ai-models-for-real-world-applications-4j4k
Title: Agent that helps with generating domains for your next projects, URL: https://dev.to/dheeraj_69411ce7c98abc201/agent-that-helps-with-generating-domains-for-your-next-projects-6dd
Title: The AI Agent Revolution: How It Will Transform Life, Work, and Business, URL: https://dev.to/dahami_fabbio/the-ai-agent-revolution-how-it-will-transform-life-work-and-business-154d
Title: Test Data Management Tools: A Complete Guide, URL: https://dev.to/keploy/test-data-management-tools-a-complete-guide-2jb7
❯ 
❯ /home/kasr/Acedmics/3rd_year/project/mento-env/bin/python /home/kasr/Acedmics/3rd_year/project/mento_repo/models/technologyUpdatess/extractArticles.py
Title: Congrats to the GitHub Copilot 1-Day Build Challenge Winners!, URL: https://dev.to/devteam/congrats-to-the-github-copilot-1-day-build-challenge-winners-4iok
Title: Exploring OpenAI Operator, URL: https://dev.to/burcs/exploring-openai-operator-your-ai-powered-browser-assistant-3dj2
Title: You don't know it, but your open-source might be worth millions of dollars 🤑, URL: https://dev.to/nevodavid/you-dont-know-it-but-your-open-source-might-be-worth-millions-of-dollars-47c
Title: Introducing Jolt: AI Codegen and Chat for 100K to Multi-Million Line Codebases, URL: https://dev.to/yev_yev_yev/introducing-jolt-ai-codegen-and-chat-for-100k-to-multi-million-line-codebases-1764
Title: Tester in 2025: Can Artificial Intelligence Replace Us?, URL: https://dev.to/leo_scott_357f10236fabe00/tester-in-2025-can-artificial-intelligence-replace-us-7jd
Title: How ContentCraft Repurposes Your Blog Posts with AI, URL: https://dev.to/ifihan/how-contentcraft-repurposes-your-blog-posts-with-ai-573g
Title: Agent that helps with generating domains for your next projects, URL: https://dev.to/dheeraj_69411ce7c98abc201/agent-that-helps-with-generating-domains-for-your-next-projects-6dd
Title: How to Train AI Models for Real-World Applications?, URL: https://dev.to/julioherreravelutini/how-to-train-ai-models-for-real-world-applications-4j4k
Title: Test Data Management Tools: A Complete Guide, URL: https://dev.to/keploy/test-data-management-tools-a-complete-guide-2jb7
Title: Test Data Management Tools: A Complete Guide, URL: https://dev.to/keploy/test-data-management-tools-a-complete-guide-1h45
Title: Irony in My AI Engineering Journey, URL: https://dev.to/dave_kabera/irony-in-my-ai-engineering-journey-4amj
Title: Vision Parse: Transform Scanned PDFs into Perfect Markdown with AI Magic ✨, URL: https://dev.to/harsha_sahu_45ed53c4c12/vision-parse-transform-scanned-pdfs-into-perfect-markdown-with-ai-magic-4920
Title: Hyped tech Updates in 2024 at a glance, What you missed?, URL: https://dev.to/arif-un/hyped-tech-updates-in-2024-at-a-glance-what-you-missed-57a0
Title: AI Gets Smarter by Double-Checking Its Work: New Self-Reflection System Shows 15% Accuracy Boost, URL: https://dev.to/mikeyoung44/ai-gets-smarter-by-double-checking-its-work-new-self-reflection-system-shows-15-accuracy-boost-48ee
Title: Test Automation Tools: A Comprehensive Guide, URL: https://dev.to/keploy/test-automation-tools-a-comprehensive-guide-4bao
Title: Flux vs Midjourney: An Honest Guide for Content Creators, URL: https://dev.to/cloudnative_eng/flux-vs-midjourney-an-honest-guide-for-content-creators-b9n
Title: The Effect of Knowledge on Efficiency Part 3, URL: https://dev.to/ourai/the-effect-of-knowledge-on-efficiency-part-3-3api
Title: AI Models Get Human-Like Memory with New Test-Time Regression Framework, URL: https://dev.to/mikeyoung44/ai-models-get-human-like-memory-with-new-test-time-regression-framework-17hj
Title: The Key Challenges of Artificial Intelligence, URL: https://dev.to/scitech-insights/the-key-challenges-of-artificial-intelligence-4ih0
Title: How to Choose the Right Generative AI Consulting Partner for Your Needs, URL: https://dev.to/smart_data_/how-to-choose-the-right-generative-ai-consulting-partner-for-your-needs-38pb
Title: How I Increased Engagement as a Content Creator Using Visual Storytelling, URL: https://dev.to/jihoonclips/how-i-increased-engagement-as-a-content-creator-using-visual-storytelling-1edh
Title: How I Transformed Educational Content Into Captivating Visual Lessons, URL: https://dev.to/grace_vo/how-i-transformed-educational-content-into-captivating-visual-lessons-1o40
Title: 🗽 Top 5 DevOps AI Tools for 2025, URL: https://dev.to/cicube/top-5-devops-ai-tools-for-2025-146l
Title: How I Made Tech Products Easier to Sell With Video Demos, URL: https://dev.to/kate_writer/how-i-made-tech-products-easier-to-sell-with-video-demos-20dm
Title: Real-World Applications of Distributed GPUs, URL: https://dev.to/neurolov_ai_/real-world-applications-of-distributed-gpus-3bp5
Title: AI Agents in Sales and Marketing, URL: https://dev.to/laxita01/ai-agents-in-sales-and-marketing-4eal
Title: The Role of AI in Improving Viewer Engagement on eSports Streams, URL: https://dev.to/entyx/the-role-of-ai-in-improving-viewer-engagement-on-esports-streams-5cda
Title: Applications of intelligent automation, URL: https://dev.to/william_lopez_69bde172f1d/applications-for-intelligent-automation-4a76
Title: How to Deploy an Eliza AI Agent on Railway, URL: https://dev.to/brolag/how-to-deploy-eliza-starter-on-railway-2pbn
Title: Trump Administration's $500B Stargate AI Project Sparks Ambition and Controversy in the Global AI Race 👀, URL: https://dev.to/arbisoftcompany/trump-administrations-500b-stargate-ai-project-sparks-ambition-and-controversy-in-the-global-ai-1k72
Title: The Role of AI in Strengthening Cybersecurity Defenses, URL: https://dev.to/alex_sebastian/the-role-of-ai-in-strengthening-cybersecurity-defenses-1aop
Title: The Impact of Generative AI in BFSI: Enhancing Efficiency and Innovation, URL: https://dev.to/globalnodes/the-impact-of-generative-ai-in-bfsi-enhancing-efficiency-and-innovation-4928
Title: AI System Masters Computer Interfaces: New Tech Makes GUI Automation 3x Faster and 45% More Accurate, URL: https://dev.to/mikeyoung44/ai-system-masters-computer-interfaces-new-tech-makes-gui-automation-3x-faster-and-45-more-accurate-eh4
Title: Embrace the Age of AI: The Importance of Mastery as Your Key Advantage, URL: https://dev.to/mckanth/embrace-the-age-of-ai-the-importance-of-mastery-as-your-key-advantage-3ck7
Title: The AI Agent Revolution: How It Will Transform Life, Work, and Business, URL: https://dev.to/dahami_fabbio/the-ai-agent-revolution-how-it-will-transform-life-work-and-business-154d
Title: What are blockchain solutions and how do they work?, URL: https://dev.to/eminencetechnology/what-are-blockchain-solutions-and-how-do-they-work-1am
Title: Unlock the Magic of Images: A Quick and Easy Guide to Using the Cutting-Edge SmolVLM-500M Model, URL: https://dev.to/alexander_uspenskiy_the_great/unlock-the-magic-of-images-a-quick-and-easy-guide-to-using-the-cutting-edge-smolvlm-500m-model-366c
Title: Which is the Best Course for Ethical Hacking?, URL: https://dev.to/ankit_cyber/which-is-the-best-course-for-ethical-hacking-517i
Title: Kick Off Stream. Wrapped Up… Hack the Future: AI & Open Source Hackathon., URL: https://dev.to/abdibrokhim/kick-off-stream-wrapped-uphack-the-future-ai-open-source-hackathon-3226
Title: RepoCast, URL: https://dev.to/mkagenius/repocast-3d0j
Title: Non-numeric data for ML (Encoding Data), URL: https://dev.to/varunpenumudi/non-numeric-data-for-ml-encoding-data-3h0c
Title: Gramhir.pro AI Image Generator: An Overview of Features and Benefits, URL: https://dev.to/techyboo009/gramhirpro-ai-image-generator-an-overview-of-features-and-benefits-4gna
Title: 📰 Elon Musk publicly trashes Trump-backed Stargate AI project, clashes with OpenAI CEO Sam Altman, URL: https://dev.to/d_thiranjaya_6d3ec4552111/elon-musk-publicly-trashes-trump-backed-stargate-ai-project-clashes-with-openai-ceo-sam-altman-2n68
Title: From Idea to Reality: Readdy's story, URL: https://dev.to/explorer1/from-idea-to-reality-readdys-story-2943
Title: Top 10 AI Inference Platforms in 2025, URL: https://dev.to/lina_lam_9ee459f98b67e9d5/top-10-ai-inference-platforms-in-2025-56kd
Title: May Jolt AI be the future of production-ready AI developer tools?, URL: https://dev.to/fmerian/may-jolt-ai-be-the-future-of-production-ready-ai-developer-tools-1k80
Title: Current Date and Time for agents, URL: https://dev.to/thewebtech/current-date-and-time-for-agents-32kj
Title: How Personal Branding Videos Helped My Clients Build Trust and Authority, URL: https://dev.to/tomhistories/how-personal-branding-videos-helped-my-clients-build-trust-and-authority-k90
Title: How SaaS Billing helps energy and utility business thrive in 2025?, URL: https://dev.to/kateryna_nechet_c288b0315/how-saas-billing-helps-energy-and-utility-business-thrive-in-2025-47pl
Title: DeepSeek-R1 vs. OpenAI o1: Which AI Reasoning Model Dominates in 2025?, URL: https://dev.to/visdom_04_88f1c6e8a47fe74/deepseek-r1-vs-openai-o1-which-ai-reasoning-model-dominates-in-2025-576l
"""

# Regular expression pattern to extract title and URL
pattern = r"Title:\s*(.*?),\s*URL:\s*(https?://\S+)"

# Extracting matches
matches = re.findall(pattern, data)

# Storing extracted data in a list of dictionaries
articles = [{"title": title.strip(), "url": url.strip()} for title, url in matches]

# Printing the extracted data
for article in articles:
    print(f"Title: {article['title']}")
    print(f"URL: {article['url']}\n ")
print(f" number of articles {len(articles)}")
