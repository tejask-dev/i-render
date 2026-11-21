# I, Render licenses and credits

The [MIT license](LICENSE) covers Tejass Kaushik’s original software contributions to I, Render. Each contributor retains rights in their own work. Specifications, artwork, photographs, hardware designs and fabrication files, recordings, saved builds, and third-party materials retain their respective rights. Possession of a copy of the team repository does not grant a separate license to these materials.

## Browser distribution

The production browser bundle uses Three.js 0.186.0 (MIT), Lucide Static 0.468.0 (ISC, with Feather portions under MIT), Bricolage Grotesque and DM Sans (Fontsource packages 5.3.0, SIL Open Font License 1.1), and a Vite 7.3.8 preload helper (MIT). The build copies all six copyright and permission notices into the root of the distributed site. Retain that file when moving the built frontend. [Complete notices](frontend/public/THIRD_PARTY_LICENSES.txt) · [Locked npm dependencies](frontend/package-lock.json)

## Python installation

The launcher uses separately installed packages. Installers supply the applicable license texts, bundled-library notices and transitive dependencies with each distribution. The table records the direct pins for this release. [Requirements](requirements.txt)

| Package | Version | Upstream license |
| --- | --- | --- |
| FastAPI | 0.165.0 | MIT |
| Uvicorn | 0.54.0 | BSD-3-Clause |
| Pydantic | 2.14.4 | MIT |
| python-multipart | 0.0.34 | Apache-2.0 |
| Pillow | 13.0.0 | MIT-CMU |
| pillow-heif | 1.8.1 | BSD-3-Clause, with additional notices for libraries bundled in its wheels |
| HTTPX | 0.28.1 | BSD-3-Clause |
| NumPy | 2.5.5 | BSD-3-Clause, 0BSD, MIT, Zlib and CC0-1.0, with wheel-specific bundled-library notices |
| trimesh | 4.12.2 | MIT |
| manifold3d | 3.5.5 | Apache-2.0 |
| SciPy | 1.18.1 | BSD-3-Clause, with bundled-library notices in its distribution |

## Recognition, audio and fabrication tools

Local recognition uses an independently installed Ollama runtime and the Qwen3-VL 4B Instruct model. Local dictation uses the separately installed Whisper CLI, base.en weights and FFmpeg. The optional Gemini adapter calls a Google service with the operator’s own credentials. The repository contains the adapters. Obtain the tools and weights from their maintainers under the terms attached to the selected versions. [Ollama](https://github.com/ollama/ollama) · [Qwen model card](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct) · [Whisper](https://github.com/openai/whisper) · [FFmpeg](https://ffmpeg.org/legal.html) · [Gemini](https://ai.google.dev/gemini-api/terms)

The P1S print project contains team geometry and machine settings and G-code produced by Bambu Studio 2.9.1.70 from Bambu Lab’s P1S profile. The printer-profile material retains its upstream terms. [Versioned Bambu Studio source and notices](https://github.com/bambulab/BambuStudio/tree/v02.09.01.70) · [Printer profiles](https://github.com/bambulab/BambuStudio/tree/v02.09.01.70/resources/profiles/BBL)

## Demo assets

The reference drawings were constructed for this project. The workshop and starter illustrations were created using OpenAI image generation. The rehearsal is a recording of the workbench using those illustrations and test inputs.

The two-object reference, its saved-project photo and the drawer montages use cropped, resized or composited photographs. Each photographer’s source page is linked in the credits below. The three-variation montage also changes layout, rotation and lighting.

| Photograph | Creator | Source terms |
| --- | --- | --- |
| Radio-controlled car | Editor abcdef | [CC0 1.0](https://commons.wikimedia.org/wiki/File:Radio_controlled_car_on_ground.JPG) |
| LED flashlight | Evan-Amos | [Public domain dedication](https://commons.wikimedia.org/wiki/File:Led-flashlight.jpg) |
| CPU fan | Whityya23 | [CC0 1.0](https://commons.wikimedia.org/wiki/File:CPU_FAN.jpg) |
| AOpen optical mouse | Leon Brooks | [Public domain](https://commons.wikimedia.org/wiki/File:Red_aopen_computer_optical_mouse.jpg) |
| Pisen USB charger | Imgrenb | [CC0 1.0](https://commons.wikimedia.org/wiki/File:Pisen_MF-08EU_12W_USB_charger-0.jpg) |
