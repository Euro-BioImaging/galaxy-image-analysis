"""
Copyright 2023 Leonid Kostrykin, Biomedical Computer Vision Group, Heidelberg University.

Distributed under the MIT license.
See file LICENSE for detail or copy at https://opensource.org/licenses/MIT

"""

import argparse
import imghdr
import os
import pathlib
import shutil
import tempfile

import ray
import superdsm.automation
import superdsm.io
import superdsm.render


hyperparameters = [
    ('AF_scale', float),
    ('c2f_region_analysis/min_atom_radius', float),
    ('c2f_region_analysis_min_norm_energy_improvement', float),
    ('c2f_region_analysis_max_atom_norm_energy', float),
    ('c2f_region_analysis_max_cluster_marker_irregularity', float),
    ('dsm_alpha', float),
    ('dsm_AF_alpha', float),
    ('global_energy_minimization_betai', float),
    ('global_energy_minimization_AF_beta', float),
    ('postprocess_mask_max_distance', int),
    ('postprocess_mask_stdamp', float),
    ('postprocess_max_norm_energy', float),
    ('postprocess_min_contrast', float),
    ('postprocess_min_object_radius', float),
]


def get_param_name(key):
    return key.replace('/', '_')


def create_config(args):
    cfg = superdsm.config.Config()
    for key, _ in hyperparameters:
        value = getattr(args, get_param_name(key))
        if value is not None:
            cfg[key] = value
    return cfg


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Segmentation of cell nuclei in 2-D fluorescence microscopy images')
    parser.add_argument('image', help='Path to the input image')
    parser.add_argument('cfg', help='Path to the file containing the configuration')
    parser.add_argument('masks', help='Path to the file containing the segmentation masks')
    parser.add_argument('overlay', help='Path to the file containing the overlay of the segmentation results')
    parser.add_argument('seg_border', type=int)
    parser.add_argument('slots', type=int)
    for key, ptype in hyperparameters:
        parser.add_argument('--' + get_param_name(key), type=ptype, default=None)
    args = parser.parse_args()

    if args.slots >= 2:
        num_threads_per_process = 2
        num_processes = args.slots // num_threads_per_process
    else:
        num_threads_per_process = 1
        num_processes = 1

    os.environ['MKL_NUM_THREADS'] = str(num_threads_per_process)
    os.environ['OPENBLAS_NUM_THREADS'] = str(num_threads_per_process)
    os.environ['MKL_DEBUG_CPU_TYPE'] = '5'

    ray.init(num_cpus=num_processes, log_to_driver=True)

    with tempfile.TemporaryDirectory() as tmpdirname:
        tmpdir = pathlib.Path(tmpdirname)
        img_ext = imghdr.what(args.image)
        img_filepath = tmpdir / f'input.{img_ext}'
        shutil.copy(str(args.image), img_filepath)

        pipeline = superdsm.pipeline.create_default_pipeline()
        cfg = create_config(args)
        img = superdsm.io.imread(img_filepath)
        data, cfg, _ = superdsm.automation.process_image(pipeline, cfg, img)

        with open(args.cfg, 'w') as fp:
            cfg.dump_json(fp)

        overlay = superdsm.render.render_result_over_image(data, border_width=args.seg_border, normalize_img=False)
        superdsm.io.imwrite(args.overlay, overlay)

        masks = superdsm.render.rasterize_labels(data)
        superdsm.io.imwrite(args.masks, masks)
