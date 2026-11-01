# HAHA Story Studio — Phase 2 visual storyboard

## Outcome

Phase 2 turns an approved 60-second story into six reviewable 9:16 scene images.
It keeps image generation downstream from fact review and human script approval,
so changing a media supplier cannot change which cultural claims are allowed.

The delivery includes:

- a provider-neutral `ImageProvider` contract;
- a deterministic SVG demo provider that requires no API key or network;
- an OpenAI Image API adapter for text generation and reference-image editing;
- a visual bible covering style, palette, light, wardrobe, exclusions, and sources;
- separate artisan, product, and workshop reference uploads;
- explicit image-rights and depicted-person consent confirmation;
- six scene states with multiple variants, selection, regeneration, and replacement;
- per-scene and approve-all human controls;
- provider, model, prompt, origin, SHA-256, timestamp, and approval metadata;
- an export ZIP containing sanitized manifests, selected images, and consented
  references.

## Demo path

1. Open the artisan-side **Story Studio** and generate a script.
2. Pass Story Guardian and choose **Approve script**.
3. Save the default visual bible. Reference images are optional; uploaded images
   require the rights-and-consent checkbox.
4. Keep **Demo provider** selected and choose **Generate all missing scene images**.
5. Inspect the six-image contact sheet and individual scene variants.
6. Regenerate one scene, select a version, or upload a rights-confirmed replacement.
7. Approve scenes individually or choose **Approve all selected scene images**.
8. Download the visual storyboard ZIP.

This entire path works without a network connection or API key.

## Live image configuration

The optional OpenAI adapter reads only environment variables:

```dotenv
OPENAI_IMAGE_API_KEY=your_openai_api_key_here
OPENAI_IMAGE_MODEL=gpt-image-2
OPENAI_IMAGE_SIZE=1152x2048
OPENAI_IMAGE_QUALITY=low
```

Choose **OpenAI Image API** in Story Studio after configuring the key. If the key
is absent, the page visibly falls back to the demo provider rather than failing
the presentation.

The adapter uses the Image API generation endpoint when there are no reference
images and the edit endpoint when the visual bible contains references. The
official guide documents both paths, base64 image output, configurable size and
quality, and the possibility that GPT Image access requires organization
verification: <https://developers.openai.com/api/docs/guides/image-generation>.

## Safety and data boundary

- Image generation is impossible until the Story Project has Guardian approval
  and a named human script approval.
- Only the scene's previously reviewed image prompt and human-authored visual
  continuity settings are sent to a provider.
- Reference uploads are limited to PNG, JPEG, or WebP and 10 MB each.
- Reference images require explicit rights and depicted-person consent.
- Provider errors are sanitized and recorded on the affected scene.
- Runtime media is stored under ignored `.local/story-media`; secrets and generated
  files are not committed.
- Export manifests replace server-local paths with file names.

## Adding another supplier

Implement `ImageProvider.generate(ImageGenerationRequest) -> ImageProviderResult`.
The request already contains the final prompt, aspect ratio, and optional reference
bytes. The result returns provider/model identity, bytes, MIME type, and dimensions.
No provider may own Story Guardian rules, approvals, storage layout, or exports.

This boundary is suitable for adding DashScope, Seedream, Gemini, fal.ai, Runway,
or another image service without changing Story Studio's business state machine.
