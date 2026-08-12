# IndexTTS-2.5 checkpoint placeholder

This directory is intentionally separate from `../checkpoints`, which remains
the local IndexTTS-2.0 rollback asset directory. No model weights are bundled
or downloaded by this source synchronization.

`pinyin.vocab` is the sole non-weight file tracked in the pinned source tree;
the source manifest records its upstream-to-vendored path mapping and hash.
Install `config.yaml` and all model assets from the official IndexTTS-2.5 model
package into this directory before configuring a 2.5 runtime.
