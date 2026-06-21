import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../api/client';

interface PhotoItem {
  id: string;
  title: string;
  description: string | null;
  file_path: string;
  created_at: string;
}

export default function PhotoLibraryWallPanel() {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadTitle, setUploadTitle] = useState('');
  const [uploadDescription, setUploadDescription] = useState('');
  const [uploadSuccess, setUploadSuccess] = useState(false);

  const { data: photos, refetch } = useQuery({
    queryKey: ['wall-photos'],
    queryFn: async () => {
      const res = await api.get('/photos');
      return res.data as PhotoItem[];
    },
    refetchInterval: 60000,
  });

  const photoList = photos || [];

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    const formData = new FormData();
    const fileInput = document.getElementById('photo-file') as HTMLInputElement;
    if (!fileInput?.files?.[0]) return;

    formData.append('file', fileInput.files[0]);
    formData.append('title', uploadTitle);
    formData.append('description', uploadDescription);

    try {
      await api.post('/photos', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setUploadSuccess(true);
      setUploadTitle('');
      setUploadDescription('');
      setTimeout(() => setUploadSuccess(false), 3000);
      await refetch();
    } catch (err) {
      console.error('Upload failed:', err);
    } finally {
      setIsUploading(false);
    }
  };

  useEffect(() => {
    if (photoList.length === 0) return;

    const timer = setInterval(() => {
      setCurrentIndex((prev) => (prev + 1) % photoList.length);
    }, 5000);
    return () => clearInterval(timer);
  }, [photoList.length]);

  return (
    <div className="h-full flex flex-col p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xl font-bold text-white">Family Photos</h3>
        <button
          onClick={() => setIsUploading(!isUploading)}
          className="px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm transition"
        >
          {isUploading ? 'Cancel' : '+ Add Photo'}
        </button>
      </div>

      {isUploading && (
        <form onSubmit={handleUpload} className="mb-4 p-3 bg-white/5 rounded-lg border border-white/10">
          <input
            id="photo-file"
            type="file"
            accept="image/*"
            className="mb-2 text-sm text-white file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-blue-600 file:text-white file:cursor-pointer file:hover:bg-blue-700"
          />
          <input
            type="text"
            placeholder="Title (optional)"
            value={uploadTitle}
            onChange={(e) => setUploadTitle(e.target.value)}
            className="w-full mb-2 px-3 py-2 bg-white/10 border border-white/20 rounded-lg text-white text-sm placeholder-slate-400"
          />
          <input
            type="text"
            placeholder="Description (optional)"
            value={uploadDescription}
            onChange={(e) => setUploadDescription(e.target.value)}
            className="w-full mb-2 px-3 py-2 bg-white/10 border border-white/20 rounded-lg text-white text-sm placeholder-slate-400"
          />
          <button
            type="submit"
            disabled={isUploading}
            className="w-full px-3 py-2 bg-green-600 hover:bg-green-700 disabled:bg-green-800 rounded-lg text-sm text-white transition"
          >
            {isUploading ? 'Uploading...' : 'Upload'}
          </button>
          {uploadSuccess && (
            <p className="mt-2 text-green-400 text-sm text-center">Photo uploaded successfully!</p>
          )}
        </form>
      )}

      {photoList.length === 0 && !isUploading && (
        <div className="h-full flex items-center justify-center">
          <p className="text-slate-400 text-lg">No photos added yet</p>
        </div>
      )}

      {photoList.length > 0 && !isUploading && (
        <>
          <div className="flex-1 flex items-center justify-center">
            <div className="relative w-full h-full flex items-center justify-center">
              <img
                src={`/api/photos/serve/${photoList[currentIndex].file_path.split('/').pop()}`}
                alt={photoList[currentIndex].title}
                className="max-w-full max-h-full object-contain rounded-lg"
              />
            </div>
          </div>
          {photoList[currentIndex].title && (
            <p className="text-center mt-4 text-lg text-white/80">{photoList[currentIndex].title}</p>
          )}
          {photoList[currentIndex].description && (
            <p className="text-center mt-2 text-sm text-slate-400">{photoList[currentIndex].description}</p>
          )}
          <div className="flex justify-center gap-2 mt-4">
            {photoList.map((_, i) => (
              <button
                key={i}
                onClick={() => setCurrentIndex(i)}
                className={`w-2 h-2 rounded-full transition-all ${
                  i === currentIndex ? 'bg-white scale-125' : 'bg-white/30'
                }`}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
