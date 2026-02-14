# TerminalBench Setup for AetherPro Infrastructure

## Executive Summary

**TerminalBench 2.0** is the industry-standard benchmark for evaluating AI agents in terminal environments. It's used by Anthropic, OpenAI, and all major AI labs to measure real-world agent capabilities.

**Your Current Performance:**
- **85% success rate** on your custom benchmark
- **96.55% tool accuracy** 
- **Ready for TerminalBench** to benchmark against frontier models

**TerminalBench Scores (Current Leaderboard):**
- **OpenAI Codex CLI (GPT-5):** 49.6% (LEADER)
- **Claude Sonnet 4.5 agents:** ~45%
- **Warp Terminal Agent:** 52%
- **GPT-4.1 with Terminus:** ~30%

**Your Goal:** Benchmark **Qwen3-Next-80B-Instruct** (your "GPT-5 level" model) against these frontier models.

---

## What is TerminalBench?

### Core Concept
TerminalBench evaluates AI agents on **89 real-world terminal tasks** including:
- Compiling Linux kernel from source
- Training ML models
- Setting up servers
- Debugging systems
- Managing databases
- Automating workflows

### Why It Matters for AetherPro

1. **Fundraising Credibility:** "Our models score X% on TerminalBench" is understood by VCs
2. **Marketing Proof:** Viral comparison against GPT-5/Claude
3. **Product Validation:** Proves your sovereign AI stack works at scale
4. **Technical Benchmark:** Identifies weaknesses in tool calling, planning, recovery

### Architecture

```
┌─────────────────────────────────────────────────┐
│  TerminalBench Task (89 tasks total)            │
│  ┌──────────────────────────────────────────┐   │
│  │ 1. Instruction (English)                 │   │
│  │    "Compile Linux kernel 6.9"            │   │
│  │                                          │   │
│  │ 2. Docker Environment                    │   │
│  │    Pre-configured container              │   │
│  │                                          │   │
│  │ 3. Test Script                           │   │
│  │    Pytest verification                   │   │
│  │                                          │   │
│  │ 4. Oracle Solution                       │   │
│  │    Human-written reference               │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────┐
│  Agent Harness (e.g., Terminus)                 │
│  ┌──────────────────────────────────────────┐   │
│  │ - Connects LLM to Docker container       │   │
│  │ - Manages conversation loop              │   │
│  │ - Executes bash commands                 │   │
│  │ - Handles tool calls                     │   │
│  │ - Tracks success/failure                 │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────┐
│  Your LLM Endpoint                              │
│  https://api.blackboxaudio.tech/v1/chat/...     │
│  Model: Qwen3-Next-80B-Instruct                 │
└─────────────────────────────────────────────────┘
```

---

## Installation & Setup

### Prerequisites

**On your Flex VM or dedicated benchmark machine:**

1. **Python 3.10+** (you have this)
2. **uv** (you use this everywhere)
3. **Docker** (required for task containers)

### Step 1: Install TerminalBench

```bash
# Using uv (your preferred method)
uv tool install terminal-bench

# OR using pip
pip install terminal-bench

# Verify installation
tb --version
```

### Step 2: Clone the Repository (for tasks)

```bash
cd ~/Documents
git clone https://github.com/laude-institute/terminal-bench.git
cd terminal-bench
```

### Step 3: Configure Environment

Create `.env` file:

```bash
# Copy template
cp .env.template .env

# Edit with your settings
nano .env
```

Add:

```env
# Your LiteLLM endpoint
OPENAI_API_BASE=https://api.blackboxaudio.tech/v1

# Your API key
OPENAI_API_KEY=sk-aether-master-pro

# Model name (as registered in LiteLLM)
DEFAULT_MODEL=qwen3-next-instruct

# Optional: For concurrent runs
MAX_WORKERS=4
```

---

## Running TerminalBench

### Quick Test Run (Single Task)

```bash
# Test with one task to verify setup
tb run \
  --agent terminus \
  --model qwen3-next-instruct \
  --dataset-name terminal-bench-core \
  --dataset-version 0.1.1 \
  --n-concurrent 1 \
  --max-tasks 1
```

### Full Benchmark Run (Official Leaderboard)

```bash
# Run the full terminal-bench-core v0.1.1 (89 tasks)
tb run \
  --agent terminus \
  --model qwen3-next-instruct \
  --dataset-name terminal-bench-core \
  --dataset-version 0.1.1 \
  --n-concurrent 8 \
  --output-dir ~/Documents/benchmark-results/terminalbench
```

**Parameters Explained:**
- `--agent terminus`: Default harness (supports OpenAI-compatible APIs)
- `--model qwen3-next-instruct`: Your model name in LiteLLM
- `--dataset-name terminal-bench-core`: Official benchmark dataset
- `--dataset-version 0.1.1`: Current leaderboard version
- `--n-concurrent 8`: Run 8 tasks in parallel (adjust based on GPU capacity)
- `--output-dir`: Where to save results

### Custom Agent Harness (Advanced)

If Terminus doesn't work perfectly with your setup, you can create a custom adapter:

```bash
# View adapter documentation
cat adapters/README.md

# Create custom adapter at:
# adapters/aetherpro_adapter.py
```

Example custom adapter structure:

```python
from terminal_bench.adapters import BaseAdapter

class AetherProAdapter(BaseAdapter):
    """Adapter for AetherPro's agent infrastructure."""
    
    def __init__(self, model: str, endpoint: str, api_key: str):
        self.model = model
        self.endpoint = endpoint
        self.api_key = api_key
    
    def run_task(self, task_instruction: str, container_id: str):
        """Execute a single task."""
        # Your agent logic here
        # Similar to your agent_benchmark.py
        pass
```

---

## Understanding Results

### Output Structure

```
~/Documents/benchmark-results/terminalbench/
├── results.json              # Full detailed results
├── summary.json             # High-level metrics
├── leaderboard_submission.json  # For official submission
└── logs/
    ├── task_001.log
    ├── task_002.log
    └── ...
```

### Key Metrics

From `summary.json`:

```json
{
  "overall_success_rate": 0.485,  // Your score: 48.5%
  "total_tasks": 89,
  "tasks_passed": 43,
  "tasks_failed": 46,
  "avg_completion_time_seconds": 180,
  "categories": {
    "software_engineering": {
      "success_rate": 0.55,
      "tasks": 20
    },
    "system_administration": {
      "success_rate": 0.42,
      "tasks": 18
    },
    "data_processing": {
      "success_rate": 0.51,
      "tasks": 15
    },
    // ... more categories
  }
}
```

### Comparing to Your Custom Benchmark

**Your Benchmark:**
- **85% success rate** on 20 tasks
- Tasks designed for your specific tools
- Mock data, deterministic results

**TerminalBench:**
- **~30-50% success rate** (frontier models)
- Real-world tasks with actual verification
- Complex multi-step reasoning required
- Full Docker environments
- Internet access allowed

**Expected Performance:**
Given your 85% on custom tasks with 96.55% tool accuracy, you should expect:
- **40-55% on TerminalBench** (competitive with Claude Sonnet 4.5)
- Higher success on file operations (your 100% benchmark category)
- Lower success on complex multi-step tasks (kernel compilation, ML training)

---

## Optimization Strategy

### Phase 1: Baseline (Week 1)
1. Run TerminalBench with default settings
2. Identify failure patterns
3. Document error categories

### Phase 2: Tool Optimization (Week 2)
1. Analyze which tool calls fail most
2. Improve argument validation
3. Add retry logic where needed
4. Test on failed tasks

### Phase 3: Prompt Engineering (Week 3)
1. Customize system prompt for TerminalBench tasks
2. Add task-specific reasoning patterns
3. Improve multi-step planning
4. Re-run benchmark

### Phase 4: Model Fine-tuning (Month 2)
1. Collect successful trajectories
2. Fine-tune on TerminalBench-style tasks
3. Run ablation studies
4. Submit to official leaderboard

---

## Connecting to Your Infrastructure

### Using Your Existing LiteLLM Proxy

**Already configured** at `https://api.blackboxaudio.tech/v1`

TerminalBench's Terminus agent uses OpenAI-compatible APIs, so it should work directly:

```bash
# Set environment variables
export OPENAI_API_BASE=https://api.blackboxaudio.tech/v1
export OPENAI_API_KEY=sk-aether-master-pro

# Run benchmark
tb run --agent terminus --model qwen3-next-instruct --dataset-name terminal-bench-core --dataset-version 0.1.1
```

### Using Harbor (New Framework)

For more advanced control, use **Harbor** (released with TerminalBench 2.0):

```bash
# Install Harbor
uv tool install harbor-framework

# Run with Harbor
harbor run \
  --model qwen3-next-instruct \
  --endpoint https://api.blackboxaudio.tech/v1 \
  --benchmark terminal-bench-core \
  --version 0.1.1 \
  --cloud-provider modal  # or daytona
```

Harbor benefits:
- Better cloud container orchestration
- Integrated with Modal/Daytona for scaling
- Tens of thousands of rollouts tested
- Built specifically for TerminalBench 2.0

---

## Submitting to Official Leaderboard

### Requirements

1. **Run on terminal-bench-core v0.1.1** (the official dataset)
2. **Use Terminus 2 harness** (or equivalent verified adapter)
3. **Generate leaderboard_submission.json**
4. **Include model card and reproducibility info**

### Submission Process

1. **Run Benchmark:**
```bash
tb run \
  --agent terminus \
  --model qwen3-next-instruct \
  --dataset-name terminal-bench-core \
  --dataset-version 0.1.1 \
  --n-concurrent 8 \
  --generate-submission
```

2. **Review Results:**
```bash
cat leaderboard_submission.json
```

3. **Submit via GitHub:**
```bash
# Fork the terminal-bench repo
# Add your results to submissions/
# Open PR with your submission
```

4. **Required Info:**
- Model name and version
- Hardware used (L40S-180, 2x48GB)
- Number of parameters (80B)
- Whether model has internet access during tasks
- Reproducibility instructions

### Leaderboard Structure

```
Model                      Success Rate   Category          Org
─────────────────────────────────────────────────────────────────
OpenAI Codex CLI (GPT-5)   49.6%         Proprietary       OpenAI
Warp Terminal Agent        52.0%         Commercial        Warp
Claude Sonnet 4.5          45.0%         Proprietary       Anthropic
GPT-4.1 + Terminus         30.0%         Proprietary       OpenAI
──────────────────────────────────────────────────────────────────
Qwen3-Next-80B (AetherPro) XX.X%         Open Source       AetherPro
```

---

## Integration with Your Existing Benchmarking

### Compare Your Custom Benchmark vs TerminalBench

**Run Both:**

```bash
# 1. Your custom benchmark
python ~/Documents/agent_benchmark.py \
  --model qwen3-next-instruct \
  --endpoint https://api.blackboxaudio.tech/v1/chat/completions \
  --num-tests 100

# 2. TerminalBench
tb run \
  --agent terminus \
  --model qwen3-next-instruct \
  --dataset-name terminal-bench-core \
  --dataset-version 0.1.1
```

**Analysis Script:**

```python
import json

# Load your benchmark results
with open('benchmark-results-tasks-summary.md') as f:
    custom_results = json.load(f)

# Load TerminalBench results
with open('~/Documents/benchmark-results/terminalbench/summary.json') as f:
    tb_results = json.load(f)

# Compare
print(f"Custom Benchmark Success: {custom_results['total_success_rate']:.1%}")
print(f"TerminalBench Success: {tb_results['overall_success_rate']:.1%}")
print(f"Gap: {(custom_results['total_success_rate'] - tb_results['overall_success_rate']):.1%}")
```

### Create Unified Dashboard

Track both benchmarks over time:

```
AetherPro Benchmark Dashboard
─────────────────────────────────────────────────
Metric                  Custom    TerminalBench
─────────────────────────────────────────────────
Success Rate            85%       48%
Tool Accuracy           96.5%     N/A
Avg Latency             1,733ms   varies
Multi-step Reasoning    80%       35%
Failure Recovery        80%       varies
─────────────────────────────────────────────────
```

---

## Cost & Resource Planning

### Compute Requirements

**Per Full Benchmark Run:**
- **89 tasks** × **~3-5 minutes per task** = **4-7 hours total**
- **With 8 concurrent tasks:** ~30-45 minutes
- **GPU utilization:** Continuous inference on L40S-180
- **VRAM:** 80B model fully loaded (~80GB)

**OVHcloud Credits:**
- You have **$5,500+ accumulated**, scaling to **$10K/month**
- One full TerminalBench run: **~$50-100** in compute (rough estimate)
- You can afford **50-100 runs** with current credits

### Recommended Cadence

**Development Phase:**
- Run **weekly** while optimizing (4 runs/month)
- Cost: **~$200-400/month**

**Production Phase:**
- Run **on each model release**
- Run **before investor demos**
- Cost: **~$100-200/month**

---

## Marketing Strategy

### Messaging

**If you score 45-50%:**
> "AetherPro's Qwen3-Next-80B achieves 48% on TerminalBench, matching Claude Sonnet 4.5 performance at a fraction of the cost, running on sovereign infrastructure."

**If you score 50%+:**
> "AetherPro breaks into top-3 on TerminalBench, demonstrating that open-source sovereign AI can compete with proprietary frontier models."

**If you score 35-45%:**
> "AetherPro's early results on TerminalBench (42%) validate our sovereign AI infrastructure, with identified optimization pathways to match frontier performance."

### Content Opportunities

1. **Blog Post:** "How We Benchmarked Our Sovereign AI Stack Against GPT-5"
2. **Twitter Thread:** Live-tweeting the benchmark run
3. **Pitch Deck Slide:** TerminalBench score vs competitors
4. **GitHub Repo:** "AetherPro TerminalBench Reproduction Guide"

---

## Next Steps

### This Week

1. **Install TerminalBench** on Flex VM or dedicated machine
2. **Run single task test** to verify setup
3. **Run full benchmark** (overnight)
4. **Analyze results** and identify failure patterns

### Next Week

1. **Optimize tool calling** based on failures
2. **Re-run specific failed tasks**
3. **Document findings** for engineering team

### This Month

1. **Submit to official leaderboard**
2. **Create marketing content** around results
3. **Integrate into CI/CD** for continuous benchmarking

---

## Support & Resources

### Official Documentation
- **Website:** https://www.tbench.ai
- **Docs:** https://www.tbench.ai/docs
- **GitHub:** https://github.com/laude-institute/terminal-bench
- **Discord:** https://discord.gg/6xWPKhGDbA

### Task Examples
- **Task Gallery:** https://www.tbench.ai/tasks
- **Leaderboard:** https://www.tbench.ai/leaderboard

### Community
- **Discord:** Join for support, share results
- **GitHub Issues:** Report bugs, request features
- **Twitter:** @TerminalBench for updates

---

## Troubleshooting

### Common Issues

**Issue: Docker permission denied**
```bash
sudo usermod -aG docker $USER
newgrp docker
```

**Issue: Model not responding**
```bash
# Test your endpoint directly
curl -X POST https://api.blackboxaudio.tech/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-aether-master-pro" \
  -d '{
    "model": "qwen3-next-instruct",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

**Issue: Tasks timing out**
```bash
# Increase timeout in config
tb run --max-task-timeout 1200  # 20 minutes instead of default
```

**Issue: Container networking**
```bash
# Ensure Docker network is configured
docker network ls
docker network inspect bridge
```

---

## Conclusion

**TerminalBench is the industry-standard benchmark that will:**
1. Validate your sovereign AI infrastructure
2. Provide credible metrics for fundraising
3. Identify optimization opportunities
4. Position AetherPro against frontier models

**Your immediate next step:** Install and run a test task to verify your setup works with your LiteLLM proxy.

**Expected timeline:** First results within 24 hours, full benchmark within this week.

**Marketing opportunity:** First open-source sovereign AI platform to publish TerminalBench results comparing to GPT-5/Claude.

---

*This guide was created for Cory Gibson / AetherPro Technologies LLC on Feb 13, 2026*
