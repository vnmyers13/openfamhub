import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";

interface PhotoItem {
  id: string;
  title: string;
  description: string | null;
  file_path: string;
  created_at: string;
}

export default function PhotosPage() {
  const [showForm, setShowForm] = useState(false);
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadDescription, setUploadDescription] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data: photos = [], isLoading } = useQuery({
    queryKey: ["photos"],
    queryFn: async () => {
      const res = await api.get('/photos');
      return res.data as PhotoItem[];
    },
  });

  const uploadPhoto = useMutation({
    mutationFn: async (data: { file: File; title: string; description: string }) => {
      const formData = new FormData();
      formData.append('file', data.file);
      formData.append('title', data.title);
      formData.append('description', data.description);
      const res = await api.post('/photos', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["photos"] });
      setUploadTitle("");
      setUploadDescription("");
      setSelectedFile(null);
      setPreviewUrl(null);
      setShowForm(false);
    },
    onError: (error) => {
      console.error('Upload failed:', error);
      alert('Failed to upload photo. Please try again.');
    },
  });

  const deletePhoto = useMutation({
    mutationFn: async (photoId: string) => {
      await api.delete(`/photos/${photoId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["photos"] });
    },
  });

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setPreviewUrl(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedFile) {
      uploadPhoto.mutate({ file: selectedFile, title: uploadTitle, description: uploadDescription });
    }
  };

  const handleDelete = (photoId: string) => {
    if (window.confirm("Delete this photo?")) {
      deletePhoto.mutate(photoId);
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const getPhotoUrl = (filePath: string) => {
    const filename = filePath.split('/').pop();
    return `/api/photos/serve/${filename}`;
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-white">Photo Library</h2>
        <button
          onClick={() => setShowForm(true)}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
        >
          + Upload Photo
        </button>
      </div>

      {showForm && (
        <div className="mb-6 bg-slate-800/50 backdrop-blur rounded-xl p-4 border border-slate-700">
          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="block text-sm text-slate-400 mb-2">Photo *</label>
              <input
                type="file"
                accept="image/*"
                required
                onChange={handleFileSelect}
                className="w-full text-sm text-white file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-blue-600 file:text-white file:cursor-pointer file:hover:bg-blue-700"
              />
            </div>

            {previewUrl && (
              <div className="relative">
                <img
                  src={previewUrl}
                  alt="Preview"
                  className="w-full max-h-64 object-contain rounded-lg bg-slate-700"
                />
              </div>
            )}

            <input
              type="text"
              placeholder="Title (optional)"
              value={uploadTitle}
              onChange={(e) => setUploadTitle(e.target.value)}
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <input
              type="text"
              placeholder="Description (optional)"
              value={uploadDescription}
              onChange={(e) => setUploadDescription(e.target.value)}
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <div className="flex gap-3 justify-end">
              <button
                type="button"
                onClick={() => {
                  setShowForm(false);
                  setUploadTitle("");
                  setUploadDescription("");
                  setSelectedFile(null);
                  setPreviewUrl(null);
                }}
                className="px-4 py-2 bg-slate-600 hover:bg-slate-700 text-white rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={!selectedFile || uploadPhoto.isPending}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
              >
                {uploadPhoto.isPending ? "Uploading..." : "Upload"}
              </button>
            </div>
          </form>
        </div>
      )}

      {isLoading ? (
        <div className="text-center text-slate-400 py-8">Loading...</div>
      ) : photos.length === 0 ? (
        <div className="text-center text-slate-400 py-8 bg-slate-800/30 rounded-xl">
          <p className="text-lg mb-2">No photos yet</p>
          <p className="text-sm">Upload your first photo to get started</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {photos.map((photo) => (
            <div
              key={photo.id}
              className="bg-slate-800/50 backdrop-blur rounded-xl overflow-hidden border border-slate-700 group"
            >
              <div className="relative">
                <img
                  src={getPhotoUrl(photo.file_path)}
                  alt={photo.title}
                  className="w-full h-48 object-cover"
                />
                <button
                  onClick={() => handleDelete(photo.id)}
                  className="absolute top-2 right-2 p-1 bg-red-600/80 hover:bg-red-600 text-white rounded-lg opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
              <div className="p-4">
                {photo.title && (
                  <h3 className="text-white font-medium mb-1">{photo.title}</h3>
                )}
                {photo.description && (
                  <p className="text-slate-400 text-sm mb-2">{photo.description}</p>
                )}
                <p className="text-slate-500 text-xs">{formatDate(photo.created_at)}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
