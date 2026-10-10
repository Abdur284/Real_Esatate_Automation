"""
Layer 1 of the 2D -> 3D pipeline: understanding a 2D floor-plan image.

    image bytes
      -> image_io      content-sniffed, size- and pixel-limited decoding; a plan
                       exported by HAVEN's own 2D module carries its exact
                       structured data inside the PNG and is used directly
      -> segmentation  classical computer vision (OpenCV) in pixel space:
                       wall mask, wall thickness, rooms, door/window gaps,
                       stair hatching, room fill colours
      -> text          OCR of room names and printed dimensions (optional)
      -> structure     pixels -> feet using the printed or typed dimensions,
                       wall-centreline snapping, the 2D plan JSON schema
                       (the same schema the 2D Design module produces), with
                       every value tagged detected / explicit / inferred / missing
      -> service       orchestration, validation gates and confidence scores

The output never depends on the renderer: it is the plan JSON consumed by
design3d.from_plan2d (Layer 2). No measurement is invented: without a known
scale the analysis stops and asks for the dimensions.
"""
