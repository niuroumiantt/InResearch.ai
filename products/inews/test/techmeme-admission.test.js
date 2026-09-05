import { test } from 'node:test';
import assert from 'node:assert/strict';
import { admitTechmemeItem, inferTechmemeAngle } from '../src/lib/techmeme.js';

const item = (title, link = 'https://www.reuters.com/technology/story') => ({ title, link });

const KEEP = [
  'Claude, ChatGPT, and Grok are experiencing issues; Anthropic and OpenAI report errors',
  'Humain plans to raise a $2.5B fund to finance data center capacity of 250 MW',
  'Nvidia agrees to acquire Hugging Face for $12.9B',
  'Neocloud Fluidstack closed a $1.5B round led by Jane Street',
  'Opposition toppled a $100B data center project in Virginia',
  'SB Energy has 8.8GW of data center capacity and a $430B backlog',
  'HPE faces server supply constraints after signing a $3.5B deal',
  'Broadcom reports AI chip revenue up 221%',
  'Broadcom reports AI chip revenue up 221%; shares fall 5%',
  'HPE reports server supply constraints and signs a $3.5B deal; HPE falls 5%',
  'iPronics partners with Nvidia to develop an optical circuit switch',
  "Kioxia expansion is part of Japan's AI and chips investment plan",
  'CXMT begins producing HBM3E and plans to expand production',
  'Anthropic signs a $35B cloud deal for a Texas data center',
  'Google releases Gemini 3.8 Flash',
  'OpenAI releases GPT-6',
  'Nvidia unveils Blackwell',
  'Nvidia launches Personal AI Router (PAIR), a free tool that distributes local AI inference workloads across compatible computers on a network, in beta',
  'G20 nations endorse AI governance principles',
  'All G20 nations unanimously endorse the non-binding Carolina Principles, a US-proposed framework calling for a lighter touch to governing emerging tech like AI',
  'LLM Token Expenditure Index: cost per million tokens falls 40%',
  'Nvidia Rubin enters mass production',
  'Blackwell shipments double in Q3',
  'Broadcom ships Tomahawk 6 Ethernet switch for AI clusters',
  'ASML books record EUV orders on AI chip demand',
  'SK Hynix starts HBM3 mass production',
  'Micron says HBM3 demand is outstripping supply',
  'US is banning exports of AI chips to China',
  'Meta rolls out Muse Spark 1.3 in Muse Code and Meta Model API',
  'Equinix inks a deal with Nvidia to let customers run AI models on Together AI',
  'Equinix, whose stock is up 33% YTD, pushing its market cap to $100B, inks a deal with Nvidia to let customers run their AI models on the Together AI platform',
  'Sources: AI coding startup Cognition is raising ~$1B at a ~$47B valuation',
  'Anthropic says Fable 5.1 will cost 25% less because of cheaper cache reads',
  'Anthropic says Fable 5.1 will cost ~25% less than Fable 5 “for typical workloads” because of cheaper cache reads and up to ~45% less “for highly agentic work”',
  'Anthropic prices Fable 5.1 at $10/1M input tokens and $50/1M output tokens, the same as Fable 5\'s pricing, but cuts cache read pricing by 75% to $0.25/1M tokens',
  'Claude Fable 5.1 and Mythos 5.1 are Anthropic\'s first models to watermark text and file outputs; eligible groups can use the detection API, as defined by EU law',
  'OpenAI says Astra reached its Critical cybersecurity threshold',
  'Source: OpenAI\'s Astra model uses “recurrent depth”, a technique that improves cost and performance but obscures the AI\'s reasoning, making it harder to monitor',
  'Letter: OpenAI told two House Democrats that its engineers are developing “automated shutdown capabilities” for AI systems',
  'OpenAI says it plans to publicly release a version of Astra “soon” but will give access to “its most advanced cyber capabilities” only to testers and partners',
  'Frontier AI labs are stepping up biological risk testing',
  'World Labs releases a multimodal world model with camera control',
  'OpenAI releases a vision model that understands camera feeds',
  'Inside Nvidia\'s Blackwell supply chain',
  'Why HBM remains the bottleneck for AI accelerators',
  'How Nvidia built the Blackwell supply chain',
  'Meta launches Muse Voice Transcribe, its first real-time audio perception model',
  'AMD launches its MI500 GPU',
  'AMD details its MI500 GPU roadmap',
  'A US court ruled against an AI startup in a copyright case',
  'A judge dismisses an OpenAI lawsuit over model training',
  'Google files a brief supporting an AI lab in a copyright appeal',
  'A school district bars students from using AI chatbots',
  'The LA Unified School District bars ~378,000 students from using AI tools on district-provided laptops and tablets as officials review AI\'s role in classrooms',
  'OpenAI faces three new lawsuits over model training',
  'OpenAI shares details of a model that is up 20% on benchmarks',
  'OpenAI releases a model defense against prompt injection attacks',
  'Survey of data center operators finds liquid cooling adoption doubled',
  'TSMC expands AI chip capacity as iPhone demand weakens',
  'Beijing-based Moonshot files confidentially for a Hong Kong IPO',
  'HPE reports Q3 revenue up 34% YoY to $12.2B, says supply constraints continue to affect its ability to meet demand, and signs a $3.5B server deal; HPE falls 5%+',
  'LLM Token Expenditure Index: average cost per million tokens has fallen to 97 cents, part of a sharp months-long decline since hitting a high of $2.07 on May 28',
  'The UK unveils a £100M Sovereign AI R&D Procurement Scheme for domestic AI startups to improve public services, amid growing opposition to Palantir contracts',
  'The EU designates ChatGPT as a very large online search engine, and Reddit and Roblox as very large online platforms after each hit 45M monthly users in the EU',
  'Sources: OpenAI bought tens of thousands of Macs for RL, Anthropic rents them, Nvidia sees Apple as its main local AI rival as Macs gain traction with AI devs',
  'As Governor Josh Shapiro, who once pushed data centers, calls them “predatory” and sets guardrails, some in struggling western Pennsylvania welcome the projects',
  'Analysis: popular chatbots debunked false narratives spread by Russia, China, and Iran most of the time; search engine AI summaries did too, but at a lower rate',
];

const DROP = [
  'HTC rolls out $499 smart glasses with Gemini or ChatGPT',
  'TrendForce: iPhone memory costs forecast to rise 400%',
  'Anker unveils a camera AI hub with a local LLM and AI chip',
  'India-based smart ring maker Ultrahuman raised $70M, including $5M in debt, a source says at a $365M valuation, and is working with Qualcomm on a new ring',
  'How parents use AI to organize family schedules',
  'MrBeast will put Gemini in his videos under a Google deal',
  'Survey: people use ChatGPT for emotional or social queries',
  'Q&A with a researcher on the OpenAI-Hugging Face incident',
  'Rogue AI may presage self-sovereign agents',
  'Spacecraft trajectory discovered using an AI system',
  'Dyson unveils an AI-powered toothbrush',
  'Pentagon launches ChatGPT Mil and Grok for Government weapons work',
  'South Korean semiconductor exports surged 209%',
  'Dell reports quarterly earnings and briefly mentions AI',
  "A look at Tim Cook's tenure, including Apple Car, AI, and App Store disputes",
  'Exxon signs a $3.5B power deal for gas turbines',
  'Cisco signs a $3B networking deal with Vodafone',
  'NetApp expands storage capacity for enterprise backups',
  'Hasbro expands Transformers production ahead of its next film',
  'CEO says AI data centers are a bubble',
  'Trump says communities that reject data centers will end up backwards and poor',
  'Nvidia shares pop 12% after earnings',
  'Nvidia stock advances 8% after earnings',
  'Nvidia reports quarterly earnings and shares jump 10%',
  'Nvidia shares are falling 8% after quarterly earnings',
  'Nvidia stock is soaring after quarterly earnings',
  'NVDA is rallying 12% after earnings',
  '$NVDA jumps 12% after AI earnings',
  'Apple launches an AI smartphone with 1TB storage capacity',
  'Apple launches an AI smartphone whose AI chip has 2x compute capacity',
  'Apple launches an AI smartphone with HBM3 and 24GB memory capacity',
  'Nvidia launches RTX 6090 gaming GPUs as laptop demand rises',
  'BMW launches liquid cooling for EV batteries',
  'OpenAI announces its new employee cafeteria',
  'Anthropic signs a new office lease',
  'OpenAI partners with a fashion brand on a holiday campaign',
  'Nvidia announces a holiday GPU giveaway',
  'OpenAI launches a marketing campaign for ChatGPT',
  'CEO says AI data center orders will explode next year',
  'Jensen Huang says AI infrastructure sales will reach $1T by 2030',
  'Shield AI launches defense drones for battlefield surveillance',
  'Aslan AI deploys agents for the FBI and intelligence community',
  'NASA launches a satellite using AI to monitor crops',
  'A hospital launches an AI system to schedule nurses',
  'John Deere is testing JD, an AI assistant for farmers, to help with best practices and find trends based on farmers\' “field, machine, and operational data”',
  'Huskeys, which uses agentic AI to help companies block AI-driven attacks, raised a $27M Series A led by Blackstone Innovations Investments at a $100M+ valuation',
  'Sources: AI sales and marketing startup Clay is raising a round led by Wellington at a $7B pre-money valuation, up from $5B via an employee tender in January',
  'Faro, which develops data models and AI tools to speed up clinical trials, raised a $37.3M Series B co-led by Merck Global Health Innovation Fund and S32',
  'DataAgent, which is developing AI agents that autonomously fix failures inside companies\' own cloud infrastructure, emerges from stealth with a $10M pre-seed',
  'OpenAI executives visit a court to discuss AI policy',
  'A judge comments on OpenAI strategy at a conference',
  "Fermi Explorer Mission plans to launch a spacecraft by 2029, using a trajectory discovered by PSI's AI system",
  'People use ChatGPT to choose dinner',
  'Travelers use Gemini to plan vacations',
  'Samsung adds Gemini to Galaxy phones',
  'Sonos opens its speakers to AI assistants',
  'Coca-Cola partners with OpenAI on a Super Bowl ad',
  'Anthropic designs a new corporate logo',
  'Foreign drones with thermal imaging face tariffs of up to 100%',
  "Z.ai reports revenue up 400%; Z.ai's market value surged 800% since listing",
  'Anker unveils a local AI hub for its cameras with an LLM, AI chip, and 48TB storage',
];

test('Techmeme admits material AI and implicit infrastructure events', () => {
  const wrong = KEEP.map((title) => [title, admitTechmemeItem(item(title))])
    .filter(([, verdict]) => !verdict.accepted);
  assert.deepEqual(wrong, [], wrong.map(([title, v]) => `${v.reason}: ${title}`).join('\n'));
});

test('Techmeme rejects stocks, gadgets, incidental AI, chatter and military stories', () => {
  const wrong = DROP.map((title) => [title, admitTechmemeItem(item(title))])
    .filter(([, verdict]) => verdict.accepted);
  assert.deepEqual(wrong, [], wrong.map(([title, v]) => `${v.reason}: ${title}`).join('\n'));
});

test('personal social posts are rejected even when they announce a core model', () => {
  const verdict = admitTechmemeItem(item(
    'Meta says its next AI model will ship with open weights',
    'https://x.com/example/status/123',
  ));
  assert.deepEqual({ accepted: verdict.accepted, reason: verdict.reason },
    { accepted: false, reason: 'social' });
});

test('accepted infrastructure is promoted only to visible, never forced to must-read', () => {
  const verdict = admitTechmemeItem(item('Opposition toppled a $100B data center project'));
  assert.equal(verdict.accepted, true);
  assert.equal(verdict.value, 2);
  assert.equal(verdict.angle, 'infra');
  assert.equal(verdict.genre, 'compute');
  assert.equal(verdict.reason, 'core_infrastructure');
});

test('Techmeme angle inference matches whole tokens, not substrings', () => {
  assert.equal(inferTechmemeAngle('Anthropic launches a serverless coding agent'), 'models');
  assert.equal(inferTechmemeAngle('Google unveils a fabulous Gemini model'), 'models');
  assert.equal(inferTechmemeAngle('AMD launches its MI500 GPU'), 'infra');
  assert.equal(inferTechmemeAngle('A court ruled against an AI startup'), 'policy');
});
