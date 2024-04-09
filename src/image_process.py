import json
import logging
import os
import sys

import cv2
import dlib
import exifread
import psycopg2
from dotenv import find_dotenv, load_dotenv


class ImageProcessor:
    def __init__(
        self,
        db_params,
        unprocessed_path,
        processed_path,
        library_path,
        landmarks_path,
        cnn_data_path,
        debug=False,
    ):
        self.db_params = db_params
        self.unprocessed_path = unprocessed_path
        self.processed_path = processed_path
        self.library_path = library_path
        self.setup_logging(debug)
        self.conn = self.connect_to_database()
        self.detector = dlib.cnn_face_detection_model_v1(cnn_data_path)
        self.predictor = dlib.shape_predictor(landmarks_path)

    def setup_logging(self, debug):
        log_filename = "../image-processing.log"
        handlers = [logging.FileHandler(log_filename), logging.StreamHandler()]
        logging_level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=logging_level,
            format="%(asctime)s %(levelname)s [%(filename)s-%(funcName)s:%(lineno)d] %(message)s",
            handlers=handlers,
        )
        self.logger = logging.getLogger(__name__)

    def connect_to_database(self):
        try:
            conn = psycopg2.connect(**self.db_params)
            self.logger.info("Database connection established.")
            return conn
        except psycopg2.DatabaseError as e:
            self.logger.error(f"Database connection failed: {e}")
            sys.exit(1)

    def process_images(self):
        files = os.listdir(self.unprocessed_path)
        for filename in files:
            file_path = os.path.join(self.unprocessed_path, filename)
            if file_path.lower().endswith((".jpg", ".jpeg", ".png")):
                self.logger.info(f"Processing file: {filename}")
                processed_image_path = os.path.join(self.processed_path, filename)
                library_image_path = os.path.join(self.library_path, filename)
                image = self.load_image(file_path)
                self.logger.info("Loaded")
                if image is not None:
                    image, aspect_ratio, scale = self.resize_image(image)
                    faces = self.detect_faces(image)
                    landmarks = self.get_landmarks(image, faces)
                    exif_data = self.extract_exif_data(file_path)  # Extract EXIF data
                    if self.insert_image_data(
                        original_path=file_path,
                        processed_path=processed_image_path,
                        face_coordinates=json.dumps(
                            [
                                {
                                    "left": f.left(),
                                    "top": f.top(),
                                    "right": f.right(),
                                    "bottom": f.bottom(),
                                }
                                for f in faces
                            ]
                        ),
                        aspect_ratio=aspect_ratio,
                        scale=scale,
                        landmarks=json.dumps(landmarks),
                        tags=json.dumps({"tags": {}}),
                        exif_data=json.dumps(
                            exif_data
                        ),  # Include EXIF data in the insertion
                    ):
                        self.save_processed_image(image, processed_image_path)
                        self.move_to_library(file_path, library_image_path)
                    else:
                        self.logger.error(
                            f"Failed to insert metadata for {filename}. File will not be moved or saved."
                        )
            self.logger.info("Finished processing all images.")

    def load_image(self, image_path):
        image = cv2.imread(image_path)
        # self.logger.info(image)
        if image is None:
            raise ValueError("Could not open or find the image")
        return image

    def resize_image(self, image, max_size=3000):
        """Resize the image such that its largest dimension is max_size."""
        width = image.shape[1]
        height = image.shape[0]
        aspect_ratio = round(width / height, 2)
        self.logger.info(f"Aspect ratio {aspect_ratio}")
        if width > height:
            scale = round(max_size / width, 2)
        else:
            scale = round(max_size / height, 2)
        self.logger.info(f"Scale: {scale}")
        new_width = int(width * scale)
        new_height = int(height * scale)
        resized_image = cv2.resize(image, (new_width, new_height))
        return resized_image, float(aspect_ratio), float(scale)

    def detect_faces(self, image):
        self.logger.info("Beginning face detection")
        dets = self.detector(image, 0)
        self.logger.info(dets)
        face_rects = dlib.rectangles()
        face_rects.extend([d.rect for d in dets])
        self.logger.info(f"fact_rects len:{len(face_rects)}")
        return face_rects

    def get_landmarks(self, image, faces):
        self.logger.info("Beginning landmark extraction")
        landmarks = []
        if not faces:
            self.logger.debug("No faces detected for landmarks extraction.")
            return landmarks
        for face in faces:
            shape = self.predictor(image, face)
            face_landmarks = [{"x": point.x, "y": point.y} for point in shape.parts()]
            landmarks.append(face_landmarks)
        return landmarks

    def extract_exif_data(self, file_path):
        """Extract EXIF data from an image file using exifread."""
        with open(file_path, "rb") as img_file:
            exif_data = exifread.process_file(img_file)
            exif_dict = {
                tag: str(value)
                for tag, value in exif_data.items()
                if tag
                not in ["JPEGThumbnail", "TIFFThumbnail", "Filename", "EXIF MakerNote"]
            }
        return exif_dict

    def save_processed_image(self, image, path):
        cv2.imwrite(path, image)
        self.logger.info(f"Processed image saved to: {path}")

    def move_to_library(self, original_path, new_path):
        os.rename(original_path, new_path)
        self.logger.info(f"Moved original image from {original_path} to {new_path}")

    def insert_image_data(
        self,
        original_path,
        processed_path,
        face_coordinates,
        aspect_ratio,
        scale,
        landmarks,
        tags,
        exif_data,
    ):
        cur = self.conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO image_metadata (original_path, processed_path, face_coordinates, aspect_ratio, processed_scale, landmarks, tags, exif_data) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) 
                ON CONFLICT (original_path) DO UPDATE SET 
                processed_path = EXCLUDED.processed_path,
                face_coordinates = EXCLUDED.face_coordinates,
                aspect_ratio = EXCLUDED.aspect_ratio,
                processed_scale = EXCLUDED.processed_scale,
                landmarks = EXCLUDED.landmarks,
                tags = EXCLUDED.tags,
                exif_data = EXCLUDED.exif_data;""",
                (
                    original_path,
                    processed_path,
                    face_coordinates,
                    aspect_ratio,
                    scale,
                    landmarks,
                    tags,
                    exif_data,
                ),
            )
            self.conn.commit()
            self.logger.info("Metadata inserted into database successfully.")
            return True
        except psycopg2.DatabaseError as e:
            self.logger.error(f"Failed to insert data into database: {e}")
            self.conn.rollback()
            cur.close()
            self.conn.close()
            sys.exit(1)
            return False
        finally:
            cur.close()

    def __del__(self):
        if self.conn:
            self.conn.close()
            self.logger.info("Database connection closed.")


if __name__ == "__main__":
    load_dotenv(find_dotenv())
    db_params = {
        "dbname": os.getenv("POSTGRES_DB"),
        "user": os.getenv("POSTGRES_USER"),
        "password": os.getenv("POSTGRES_PASSWORD"),
        "host": os.getenv("POSTGRES_HOST"),
        "port": os.getenv("POSTGRES_PORT"),
    }
    unprocessed_path = os.getenv("UNPROCESSED_PATH")
    processed_path = os.getenv("PROCESSED_PATH")
    library_path = os.getenv("LIBRARY_PHOTOS_PATH")
    landmarks_path = os.getenv("LANDMARKS_PATH")
    cnn_data_path = os.getenv("DLIB_CNN_PATH")
    debug_mode = os.getenv("DEBUG_MODE", "False") == "True"
    processor = ImageProcessor(
        db_params,
        unprocessed_path,
        processed_path,
        library_path,
        landmarks_path,
        cnn_data_path,
        debug=debug_mode,
    )
    processor.process_images()
