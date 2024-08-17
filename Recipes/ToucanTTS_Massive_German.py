import time

import torch
import wandb
from torch.utils.data import ConcatDataset

from Modules.ToucanTTS.ToucanTTS import ToucanTTS
from Modules.ToucanTTS.toucantts_train_loop_arbiter import train_loop
from Utility.corpus_preparation import prepare_tts_corpus
from Utility.path_to_transcript_dicts import *
from Utility.storage_config import MODELS_DIR
from Utility.storage_config import PREPROCESSING_DIR


def run(gpu_id, resume_checkpoint, finetune, model_dir, resume, use_wandb, wandb_resume_id, gpu_count):
    if gpu_id == "cpu":
        device = torch.device("cpu")
    else:
        device = torch.device("cuda")

    print("Preparing")

    if model_dir is not None:
        save_dir = model_dir
    else:
        save_dir = os.path.join(MODELS_DIR, "ToucanTTS_German")
    os.makedirs(save_dir, exist_ok=True)

    if gpu_count > 1:
        rank = int(os.environ["LOCAL_RANK"])
        torch.cuda.set_device(rank)
        torch.distributed.init_process_group(backend="nccl")
    else:
        rank = 0

    datasets = list()

    datasets.append(prepare_tts_corpus(transcript_dict=build_path_to_transcript_dict_karlsson,
                                       corpus_dir=os.path.join(PREPROCESSING_DIR, "Karlsson"),
                                       lang="deu",
                                       gpu_count=gpu_count,
                                       rank=rank))

    datasets.append(prepare_tts_corpus(transcript_dict=build_path_to_transcript_dict_eva,
                                       corpus_dir=os.path.join(PREPROCESSING_DIR, "Eva"),
                                       lang="deu",
                                       gpu_count=gpu_count,
                                       rank=rank))

    datasets.append(prepare_tts_corpus(transcript_dict=build_path_to_transcript_dict_hokus,
                                       corpus_dir=os.path.join(PREPROCESSING_DIR, "Hokus"),
                                       lang="deu",
                                       gpu_count=gpu_count,
                                       rank=rank))

    datasets.append(prepare_tts_corpus(transcript_dict=build_path_to_transcript_dict_bernd,
                                       corpus_dir=os.path.join(PREPROCESSING_DIR, "Bernd"),
                                       lang="deu",
                                       gpu_count=gpu_count,
                                       rank=rank))

    datasets.append(prepare_tts_corpus(transcript_dict=build_path_to_transcript_dict_friedrich,
                                       corpus_dir=os.path.join(PREPROCESSING_DIR, "Friedrich"),
                                       lang="deu",
                                       gpu_count=gpu_count,
                                       rank=rank))

    datasets.append(prepare_tts_corpus(transcript_dict=build_path_to_transcript_dict_hui_others,
                                       corpus_dir=os.path.join(PREPROCESSING_DIR, "hui_others"),
                                       lang="deu",
                                       gpu_count=gpu_count,
                                       rank=rank))

    datasets.append(prepare_tts_corpus(transcript_dict=build_path_to_transcript_dict_thorsten_emotional(),
                                       corpus_dir=os.path.join(PREPROCESSING_DIR, "thorsten_emotional"),
                                       lang="deu",
                                       gpu_count=gpu_count,
                                       rank=rank))

    datasets.append(prepare_tts_corpus(transcript_dict=build_path_to_transcript_dict_thorsten_neutral(),
                                       corpus_dir=os.path.join(PREPROCESSING_DIR, "thorsten_neutral"),
                                       lang="deu",
                                       gpu_count=gpu_count,
                                       rank=rank))

    datasets.append(prepare_tts_corpus(transcript_dict=build_path_to_transcript_dict_thorsten_2022_10(),
                                       corpus_dir=os.path.join(PREPROCESSING_DIR, "thorsten_2022"),
                                       lang="deu",
                                       gpu_count=gpu_count,
                                       rank=rank))

    chunk_count = 20
    chunks = split_dictionary_into_chunks(build_path_to_transcript_dict_mls_german(), split_n=chunk_count)
    for index in range(chunk_count):
        datasets.append(prepare_tts_corpus(transcript_dict=chunks[index],
                                           corpus_dir=os.path.join(PREPROCESSING_DIR, f"mls_german_chunk_{index}"),
                                           lang="deu",
                                           gpu_count=gpu_count,
                                           rank=rank))

    train_set = ConcatDataset(datasets)

    model = ToucanTTS()

    if gpu_count > 1:
        model.to(rank)
        model = torch.nn.parallel.DistributedDataParallel(
            model,
            device_ids=[rank],
            output_device=rank,
            find_unused_parameters=True,
        )
        torch.distributed.barrier()
    train_sampler = torch.utils.data.RandomSampler(train_set)

    if use_wandb:
        if rank == 0:
            wandb.init(
                name=f"{__name__.split('.')[-1]}_{time.strftime('%Y%m%d-%H%M%S')}" if wandb_resume_id is None else None,
                id=wandb_resume_id,  # this is None if not specified in the command line arguments.
                resume="must" if wandb_resume_id is not None else None)
    print("Training model")
    train_loop(net=model,
               datasets=[train_set],
               batch_size=12,
               steps_per_checkpoint=1000,
               device=device,
               save_directory=save_dir,
               eval_lang="deu",
               path_to_checkpoint=resume_checkpoint,
               fine_tune=finetune,
               resume=resume,
               use_wandb=use_wandb,
               train_samplers=[train_sampler],
               gpu_count=gpu_count)
    if use_wandb:
        wandb.finish()
