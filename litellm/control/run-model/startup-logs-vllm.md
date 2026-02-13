ubuntu@l40s-180-us-west-or-1:~/aether-model-node/control/run-model$ docker-compose logs -f
Attaching to qwen3-next-instruct
qwen3-next-instruct | WARNING 02-12 19:46:23 [argparse_utils.py:195] With `vllm serve`, you should provide the model as a positional argument or in a config file instead of via the `--model` option. The `--model` option will be removed in v0.13.
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:46:23 [api_server.py:1351] vLLM API server version 0.13.0
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:46:23 [utils.py:253] non-default args: {'model_tag': '/models', 'host': '0.0.0.0', 'port': 8001, 'enable_auto_tool_choice': True, 'tool_call_parser': 'hermes', 'model': '/models', 'max_model_len': 32768, 'served_model_name': ['qwen3-next-instruct'], 'generation_config': 'vllm', 'tensor_parallel_size': 2, 'disable_custom_all_reduce': True, 'gpu_memory_utilization': 0.92, 'swap_space': 8.0, 'kv_cache_dtype': 'fp8', 'enable_prefix_caching': True, 'max_num_batched_tokens': 8192, 'max_num_seqs': 8}
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:46:30 [model.py:514] Resolved architecture: Qwen3NextForCausalLM
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:46:30 [model.py:1661] Using max model len 32768
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:46:30 [cache.py:205] Using fp8 data type to store kv cache. It reduces the GPU memory footprint and boosts the performance. Meanwhile, it may cause accuracy drop without a proper scaling factor.
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:46:30 [scheduler.py:230] Chunked prefill is enabled with max_num_batched_tokens=8192.
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:46:30 [config.py:302] Hybrid or mamba-based model detected without support for prefix caching: disabling.
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:46:30 [config.py:312] Disabling cascade attention since it is not supported for hybrid models.
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:46:31 [config.py:439] Setting attention block size to 1072 tokens to ensure that attention page size is >= mamba page size.
qwen3-next-instruct | (APIServer pid=1) The tokenizer you are loading from '/models' with an incorrect regex pattern: https://huggingface.co/mistralai/Mistral-Small-3.1-24B-Instruct-2503/discussions/84#69121093e8b480e709447d5e. This will lead to incorrect tokenization. You should set the `fix_mistral_regex=True` flag when loading this tokenizer to fix this issue.
qwen3-next-instruct | (EngineCore_DP0 pid=241) INFO 02-12 19:46:37 [core.py:93] Initializing a V1 LLM engine (v0.13.0) with config: model='/models', speculative_config=None, tokenizer='/models', skip_tokenizer_init=False, tokenizer_mode=auto, revision=None, tokenizer_revision=None, trust_remote_code=False, dtype=torch.bfloat16, max_seq_len=32768, download_dir=None, load_format=auto, tensor_parallel_size=2, pipeline_parallel_size=1, data_parallel_size=1, disable_custom_all_reduce=True, quantization=compressed-tensors, enforce_eager=False, kv_cache_dtype=fp8, device_config=cuda, structured_outputs_config=StructuredOutputsConfig(backend='auto', disable_fallback=False, disable_any_whitespace=False, disable_additional_properties=False, reasoning_parser='', reasoning_parser_plugin='', enable_in_reasoning=False), observability_config=ObservabilityConfig(show_hidden_metrics_for_version=None, otlp_traces_endpoint=None, collect_detailed_traces=None, kv_cache_metrics=False, kv_cache_metrics_sample=0.01, cudagraph_metrics=False, enable_layerwise_nvtx_tracing=False), seed=0, served_model_name=qwen3-next-instruct, enable_prefix_caching=False, enable_chunked_prefill=True, pooler_config=None, compilation_config={'level': None, 'mode': <CompilationMode.VLLM_COMPILE: 3>, 'debug_dump_path': None, 'cache_dir': '', 'compile_cache_save_format': 'binary', 'backend': 'inductor', 'custom_ops': ['none'], 'splitting_ops': ['vllm::unified_attention', 'vllm::unified_attention_with_output', 'vllm::unified_mla_attention', 'vllm::unified_mla_attention_with_output', 'vllm::mamba_mixer2', 'vllm::mamba_mixer', 'vllm::short_conv', 'vllm::linear_attention', 'vllm::plamo2_mamba_mixer', 'vllm::gdn_attention_core', 'vllm::kda_attention', 'vllm::sparse_attn_indexer'], 'compile_mm_encoder': False, 'compile_sizes': [], 'compile_ranges_split_points': [8192], 'inductor_compile_config': {'enable_auto_functionalized_v2': False, 'combo_kernels': True, 'benchmark_combo_kernel': True}, 'inductor_passes': {}, 'cudagraph_mode': <CUDAGraphMode.FULL_AND_PIECEWISE: (2, 1)>, 'cudagraph_num_of_warmups': 1, 'cudagraph_capture_sizes': [1, 2, 4, 8, 16], 'cudagraph_copy_inputs': False, 'cudagraph_specialize_lora': True, 'use_inductor_graph_partition': False, 'pass_config': {'fuse_norm_quant': False, 'fuse_act_quant': False, 'fuse_attn_quant': False, 'eliminate_noops': True, 'enable_sp': False, 'fuse_gemm_comms': False, 'fuse_allreduce_rms': False}, 'max_cudagraph_capture_size': 16, 'dynamic_shapes_config': {'type': <DynamicShapesType.BACKED: 'backed'>, 'evaluate_guards': False}, 'local_cache_dir': None}
qwen3-next-instruct | (EngineCore_DP0 pid=241) WARNING 02-12 19:46:37 [multiproc_executor.py:882] Reducing Torch parallelism from 30 threads to 1 to avoid unnecessary CPU contention. Set OMP_NUM_THREADS in the external environment to tune this value as needed.
qwen3-next-instruct | INFO 02-12 19:46:44 [parallel_state.py:1203] world_size=2 rank=0 local_rank=0 distributed_init_method=tcp://127.0.0.1:50255 backend=nccl
qwen3-next-instruct | INFO 02-12 19:46:44 [parallel_state.py:1203] world_size=2 rank=1 local_rank=1 distributed_init_method=tcp://127.0.0.1:50255 backend=nccl
qwen3-next-instruct | INFO 02-12 19:46:44 [pynccl.py:111] vLLM is using nccl==2.27.5
qwen3-next-instruct | WARNING 02-12 19:46:44 [symm_mem.py:67] SymmMemCommunicator: Device capability 8.9 not supported, communicator is not available.
qwen3-next-instruct | WARNING 02-12 19:46:44 [symm_mem.py:67] SymmMemCommunicator: Device capability 8.9 not supported, communicator is not available.
qwen3-next-instruct | INFO 02-12 19:46:44 [parallel_state.py:1411] rank 1 in world size 2 is assigned as DP rank 0, PP rank 0, PCP rank 0, TP rank 1, EP rank 1
qwen3-next-instruct | INFO 02-12 19:46:44 [parallel_state.py:1411] rank 0 in world size 2 is assigned as DP rank 0, PP rank 0, PCP rank 0, TP rank 0, EP rank 0
qwen3-next-instruct | (Worker_TP0 pid=306) INFO 02-12 19:46:45 [gpu_model_runner.py:3562] Starting to load model /models...
qwen3-next-instruct | (Worker_TP0 pid=306) WARNING 02-12 19:46:46 [compressed_tensors.py:742] Acceleration for non-quantized schemes is not supported by Compressed Tensors. Falling back to UnquantizedLinearMethod
qwen3-next-instruct | (Worker_TP0 pid=306) INFO 02-12 19:46:46 [layer.py:372] Enabled separate cuda stream for MoE shared_experts
qwen3-next-instruct | (Worker_TP1 pid=307) WARNING 02-12 19:46:46 [compressed_tensors.py:742] Acceleration for non-quantized schemes is not supported by Compressed Tensors. Falling back to UnquantizedLinearMethod
qwen3-next-instruct | (Worker_TP0 pid=306) INFO 02-12 19:46:46 [compressed_tensors_moe.py:193] Using CompressedTensorsWNA16MarlinMoEMethod
qwen3-next-instruct | (Worker_TP1 pid=307) INFO 02-12 19:46:46 [compressed_tensors_moe.py:193] Using CompressedTensorsWNA16MarlinMoEMethod
qwen3-next-instruct | (Worker_TP0 pid=306) INFO 02-12 19:47:04 [cuda.py:351] Using FLASHINFER attention backend out of potential backends: ('FLASHINFER', 'TRITON_ATTN')
Loading safetensors checkpoint shards:   0% Completed | 0/10 [00:00<?, ?it/s]
Loading safetensors checkpoint shards:  10% Completed | 1/10 [00:04<00:41,  4.59s/it]
Loading safetensors checkpoint shards:  20% Completed | 2/10 [00:09<00:36,  4.60s/it]
Loading safetensors checkpoint shards:  30% Completed | 3/10 [00:13<00:31,  4.56s/it]
Loading safetensors checkpoint shards:  40% Completed | 4/10 [00:18<00:27,  4.59s/it]
Loading safetensors checkpoint shards:  50% Completed | 5/10 [00:23<00:23,  4.69s/it]
Loading safetensors checkpoint shards:  60% Completed | 6/10 [00:27<00:18,  4.62s/it]
Loading safetensors checkpoint shards:  70% Completed | 7/10 [00:31<00:13,  4.43s/it]
Loading safetensors checkpoint shards:  90% Completed | 9/10 [00:36<00:03,  3.40s/it]
Loading safetensors checkpoint shards: 100% Completed | 10/10 [00:40<00:00,  3.70s/it]
Loading safetensors checkpoint shards: 100% Completed | 10/10 [00:40<00:00,  4.09s/it]
qwen3-next-instruct | (Worker_TP0 pid=306) 
qwen3-next-instruct | (Worker_TP0 pid=306) INFO 02-12 19:47:46 [default_loader.py:308] Loading weights took 41.05 seconds
qwen3-next-instruct | (Worker_TP1 pid=307) WARNING 02-12 19:47:46 [kv_cache.py:90] Checkpoint does not provide a q scaling factor. Setting it to k_scale. This only matters for FP8 Attention backends (flash-attn or flashinfer).
qwen3-next-instruct | (Worker_TP1 pid=307) WARNING 02-12 19:47:46 [kv_cache.py:104] Using KV cache scaling factor 1.0 for fp8_e4m3. If this is unintended, verify that k/v_scale scaling factors are properly set in the checkpoint.
qwen3-next-instruct | (Worker_TP1 pid=307) WARNING 02-12 19:47:46 [kv_cache.py:143] Using uncalibrated q_scale 1.0 and/or prob_scale 1.0 with fp8 attention. This may cause accuracy issues. Please make sure q/prob scaling factors are available in the fp8 checkpoint.
qwen3-next-instruct | (Worker_TP0 pid=306) WARNING 02-12 19:47:46 [kv_cache.py:90] Checkpoint does not provide a q scaling factor. Setting it to k_scale. This only matters for FP8 Attention backends (flash-attn or flashinfer).
qwen3-next-instruct | (Worker_TP0 pid=306) WARNING 02-12 19:47:46 [kv_cache.py:104] Using KV cache scaling factor 1.0 for fp8_e4m3. If this is unintended, verify that k/v_scale scaling factors are properly set in the checkpoint.
qwen3-next-instruct | (Worker_TP0 pid=306) WARNING 02-12 19:47:46 [kv_cache.py:143] Using uncalibrated q_scale 1.0 and/or prob_scale 1.0 with fp8 attention. This may cause accuracy issues. Please make sure q/prob scaling factors are available in the fp8 checkpoint.
qwen3-next-instruct | (Worker_TP0 pid=306) INFO 02-12 19:47:50 [gpu_model_runner.py:3659] Model loading took 22.5313 GiB memory and 63.204064 seconds
qwen3-next-instruct | (Worker_TP0 pid=306) INFO 02-12 19:47:58 [backends.py:643] Using cache directory: /root/.cache/vllm/torch_compile_cache/ada1eb5f22/rank_0_0/backbone for vLLM's torch.compile
qwen3-next-instruct | (Worker_TP0 pid=306) INFO 02-12 19:47:58 [backends.py:703] Dynamo bytecode transform time: 7.94 s
qwen3-next-instruct | (Worker_TP1 pid=307) INFO 02-12 19:48:08 [backends.py:261] Cache the graph of compile range (1, 8192) for later use
qwen3-next-instruct | (Worker_TP0 pid=306) INFO 02-12 19:48:08 [backends.py:261] Cache the graph of compile range (1, 8192) for later use
qwen3-next-instruct | (EngineCore_DP0 pid=241) INFO 02-12 19:48:50 [shm_broadcast.py:542] No available shared memory broadcast block found in 60 seconds. This typically happens when some processes are hanging or doing some time-consuming work (e.g. compilation, weight/kv cache quantization).
qwen3-next-instruct | (EngineCore_DP0 pid=241) INFO 02-12 19:49:50 [shm_broadcast.py:542] No available shared memory broadcast block found in 60 seconds. This typically happens when some processes are hanging or doing some time-consuming work (e.g. compilation, weight/kv cache quantization).
qwen3-next-instruct | (Worker_TP0 pid=306) INFO 02-12 19:50:07 [backends.py:278] Compiling a graph for compile range (1, 8192) takes 123.77 s
qwen3-next-instruct | (Worker_TP0 pid=306) INFO 02-12 19:50:07 [monitor.py:34] torch.compile takes 131.72 s in total
qwen3-next-instruct | (Worker_TP0 pid=306) INFO 02-12 19:50:09 [gpu_worker.py:375] Available KV cache memory: 17.58 GiB
qwen3-next-instruct | (EngineCore_DP0 pid=241) INFO 02-12 19:50:09 [kv_cache_utils.py:1291] GPU KV cache size: 767,552 tokens
qwen3-next-instruct | (EngineCore_DP0 pid=241) INFO 02-12 19:50:09 [kv_cache_utils.py:1296] Maximum concurrency for 32,768 tokens per request: 84.29x
Capturing CUDA graphs (mixed prefill-decode, PIECEWISE): 100%|██████████| 5/5 [00:00<00:00,  8.53it/s]
Capturing CUDA graphs (decode, FULL): 100%|██████████| 4/4 [00:01<00:00,  2.09it/s]
qwen3-next-instruct | (Worker_TP0 pid=306) INFO 02-12 19:50:13 [gpu_model_runner.py:4587] Graph capturing finished in 4 secs, took 0.79 GiB
qwen3-next-instruct | (EngineCore_DP0 pid=241) INFO 02-12 19:50:13 [core.py:259] init engine (profile, create kv cache, warmup model) took 143.64 seconds
qwen3-next-instruct | (EngineCore_DP0 pid=241) The tokenizer you are loading from '/models' with an incorrect regex pattern: https://huggingface.co/mistralai/Mistral-Small-3.1-24B-Instruct-2503/discussions/84#69121093e8b480e709447d5e. This will lead to incorrect tokenization. You should set the `fix_mistral_regex=True` flag when loading this tokenizer to fix this issue.
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [api_server.py:1099] Supported tasks: ['generate']
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [serving_engine.py:270] "auto" tool choice has been enabled.
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [serving_engine.py:270] "auto" tool choice has been enabled.
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [serving_engine.py:270] "auto" tool choice has been enabled.
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [api_server.py:1425] Starting vLLM API server 0 on http://0.0.0.0:8001
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:38] Available routes are:
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /openapi.json, Methods: GET, HEAD
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /docs, Methods: GET, HEAD
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /docs/oauth2-redirect, Methods: GET, HEAD
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /redoc, Methods: GET, HEAD
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /scale_elastic_ep, Methods: POST
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /is_scaling_elastic_ep, Methods: POST
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /tokenize, Methods: POST
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /detokenize, Methods: POST
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /inference/v1/generate, Methods: POST
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /pause, Methods: POST
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /resume, Methods: POST
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /is_paused, Methods: GET
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /metrics, Methods: GET
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /health, Methods: GET
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /load, Methods: GET
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /v1/models, Methods: GET
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /version, Methods: GET
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /v1/responses, Methods: POST
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /v1/responses/{response_id}, Methods: GET
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /v1/responses/{response_id}/cancel, Methods: POST
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /v1/messages, Methods: POST
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /v1/chat/completions, Methods: POST
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /v1/completions, Methods: POST
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /v1/audio/transcriptions, Methods: POST
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /v1/audio/translations, Methods: POST
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /ping, Methods: GET
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /ping, Methods: POST
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /invocations, Methods: POST
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /classify, Methods: POST
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /v1/embeddings, Methods: POST
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /score, Methods: POST
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /v1/score, Methods: POST
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /rerank, Methods: POST
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /v1/rerank, Methods: POST
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /v2/rerank, Methods: POST
qwen3-next-instruct | (APIServer pid=1) INFO 02-12 19:50:14 [launcher.py:46] Route: /pooling, Methods: POST
qwen3-next-instruct | (APIServer pid=1) INFO:     Started server process [1]
qwen3-next-instruct | (APIServer pid=1) INFO:     Waiting for application startup.
qwen3-next-instruct | (APIServer pid=1) INFO:     Application startup complete.
