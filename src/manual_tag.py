import datetime
import json
import os
import sys
import tkinter as tk
from tkinter import filedialog, simpledialog

import psycopg2
from dotenv import find_dotenv, load_dotenv
from PIL import Image, ImageDraw, ImageTk


class ManualTagger:
    def __init__(self, db_params, processed_path, debug=False):
        self.db_params = db_params
        self.processed_path = processed_path
        self.debug = debug
        self.conn = self.connect_to_database()
        self.images = []  # List of image files in the processed_path
        self.current_image_index = 0  # Index of the currently displayed image

    def connect_to_database(self):
        try:
            conn = psycopg2.connect(**self.db_params)
            print("Database connection established.")
            return conn
        except psycopg2.DatabaseError as e:
            print(f"Database connection failed: {e}")
            sys.exit(1)

    def load_images(self):
        """Load all image paths from the processed directory."""
        self.images = [
            os.path.join(self.processed_path, f)
            for f in os.listdir(self.processed_path)
            if f.endswith((".jpg", ".jpeg", ".png"))
        ]
        self.images.sort()  # Optional: sort the files
        self.load_image()

    def load_image(self):
        if self.current_image_index < len(self.images):
            path = self.images[self.current_image_index]
            img = Image.open(path)
            img.thumbnail(
                (1000, 1000), Image.Resampling.LANCZOS
            )  # Updated method for resizing
            img_tk = ImageTk.PhotoImage(img)
            self.canvas.image = img_tk  # Keep reference to avoid garbage collection
            self.canvas.create_image(0, 0, image=img_tk, anchor="nw")
            self.draw_faces(path, img)
        else:
            print("No more images to display.")

    def next_image(self):
        """Move to the next image in the list."""
        if self.current_image_index < len(self.images) - 1:
            self.current_image_index += 1
            self.load_image()
        else:
            print("Reached the end of the image list. Closing...")
            sys.exit(1)

    def setup_ui(self):
        self.root = tk.Tk()
        self.root.title("Image Tagging Tool")
        self.canvas = tk.Canvas(self.root, width=1000, height=1000)
        self.canvas.bind("<Button-1>", self.on_canvas_click)  # Bind left mouse click
        self.canvas.pack()
        next_btn = tk.Button(self.root, text="Next Image", command=self.next_image)
        next_btn.pack()
        self.load_images()  # Start by loading the images
        self.root.mainloop()

    def on_canvas_click(self, event):
        # Check if click is within any face rectangle
        for face in self.current_faces:
            if (face["left"] / 3 <= event.x <= face["right"] / 3) and (
                face["top"] / 3 <= event.y <= face["bottom"] / 3
            ):
                self.tag_face(face)

    def tag_face(self, face):
        tag = simpledialog.askstring("Tag", "Enter tag for this face:")
        if tag:
            # Assuming face ID or similar identifier is available to uniquely identify the face
            self.update_face_tag(face, tag)

    def update_face_tag(self, face_id, tag):
        cur = self.conn.cursor()
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Retrieve the current tags data
        cur.execute(
            "SELECT tags FROM image_metadata WHERE processed_path = %s",
            (self.current_image_path,),
        )
        current_tags = cur.fetchone()[0]

        # If there are no current tags, initialize an empty dictionary
        if not current_tags:
            current_tags = {}

        # Format and insert new tag data
        current_tags[str(face_id["id"])] = {
            "tag": tag.title(),  # Ensures consistent capitalization
            "type": "person",  # This could be dynamic based on your tagging needs
            "last_modified": timestamp,  # Timestamp to track when the tag was updated
        }

        # Update the tags in the database
        cur.execute(
            "UPDATE image_metadata SET tags = %s WHERE processed_path = %s",
            (json.dumps(current_tags), self.current_image_path),
        )
        self.conn.commit()
        cur.close()
        print(f"Tag '{tag.title()}' added to face {face_id}")

    def draw_faces(self, image_path, img):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id, face_coordinates, tags FROM image_metadata WHERE processed_path = %s",
            (image_path,),
        )
        face_data = cur.fetchone()
        cur.close()
        self.current_image_path = image_path  # Store current path
        if face_data:
            scale = 1 / 3
            self.id = face_data[0]
            print(f"ID: {self.id}")
            tags = face_data[2]  # Load tags data
            draw = ImageDraw.Draw(img)
            self.current_faces = []  # Store current faces for click detection
            for i, face in enumerate(json.loads(face_data[1])):
                scaled_rect = [
                    face["left"] * scale,
                    face["top"] * scale,
                    face["right"] * scale,
                    face["bottom"] * scale,
                ]
                draw.rectangle(scaled_rect, outline="red", width=3)
                face_tag = tags.get(str(i), {}).get(
                    "tag", "No Tag"
                )  # Default to 'No Tag'
                draw.text(
                    (scaled_rect[0], scaled_rect[1] - 10), face_tag, fill="yellow"
                )
                face["id"] = i  # Assign an ID for tagging purposes
                self.current_faces.append(face)
            img_tk = ImageTk.PhotoImage(img)
            self.canvas.image = img_tk
            self.canvas.create_image(0, 0, image=img_tk, anchor="nw")
        else:
          self.next_image()
    def tag_images(self):
        self.setup_ui()


if __name__ == "__main__":
    load_dotenv(find_dotenv())
    db_params = {
        "dbname": os.getenv("POSTGRES_DB"),
        "user": os.getenv("POSTGRES_USER"),
        "password": os.getenv("POSTGRES_PASSWORD"),
        "host": os.getenv("POSTGRES_HOST"),
        "port": os.getenv("POSTGRES_PORT"),
    }
    processed_path = os.getenv("PROCESSED_PATH")
    debug_mode = os.getenv("DEBUG_MODE", "False") == "True"
    tagger = ManualTagger(db_params, processed_path, debug=debug_mode)
    tagger.tag_images()
