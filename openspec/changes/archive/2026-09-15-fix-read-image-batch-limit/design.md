## Context

Read aggregates image follow-up messages into one function output. Responses normalization already rejects more than eight images in that output, but by then the tool has reported success.

## Goals / Non-Goals

Return an ordinary tool error before returning an oversized image result. Keep the existing request-boundary validation as defense in depth. Do not change the request size or conversation-wide image policy.

## Decisions

Count image content blocks after collecting batch results, using the existing shared image limit. On overflow, return only an error and count/limit metadata; do not include image follow-ups. Preserve successful batches with up to eight images, including accompanying text targets.

## Risks / Trade-offs

Files are still read before aggregate validation. This small change avoids changing existing concurrent read and partial-result behavior. The error tells the model to retry with fewer images.
