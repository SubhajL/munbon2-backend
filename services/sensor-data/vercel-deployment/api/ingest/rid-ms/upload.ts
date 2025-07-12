import type { VercelRequest, VercelResponse } from '@vercel/node';
import { IncomingForm, File } from 'formidable';
import { promises as fs } from 'fs';

// Configure formidable for file uploads
export const config = {
  api: {
    bodyParser: false,
  },
};

// Bearer token validation
const VALID_BEARER_TOKEN = process.env.SHAPE_UPLOAD_TOKEN || 'munbon-ridms-shape';

export default async function handler(
  req: VercelRequest,
  res: VercelResponse
) {
  // Only accept POST
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  // Validate bearer token
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Missing bearer token' });
  }

  const token = authHeader.substring(7);
  if (token !== VALID_BEARER_TOKEN) {
    return res.status(401).json({ error: 'Invalid bearer token' });
  }

  try {
    // Parse multipart form data
    const form = new IncomingForm({
      maxFileSize: 100 * 1024 * 1024, // 100MB limit
      keepExtensions: true
    });

    const [fields, files] = await new Promise<[any, any]>((resolve, reject) => {
      form.parse(req, (err, fields, files) => {
        if (err) reject(err);
        else resolve([fields, files]);
      });
    });

    // Get the uploaded file
    const uploadedFile = Array.isArray(files.file) ? files.file[0] : files.file;
    if (!uploadedFile) {
      return res.status(400).json({ error: 'No file uploaded' });
    }

    // Validate file type (should be .zip for shapefiles)
    if (!uploadedFile.originalFilename?.endsWith('.zip')) {
      return res.status(400).json({ 
        error: 'Invalid file type. Please upload a ZIP file containing shapefile components' 
      });
    }

    // Read file data
    const fileData = await fs.readFile(uploadedFile.filepath);
    
    // Generate upload ID
    const uploadId = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

    // For Vercel, we have several storage options:
    
    // Option 1: Use Vercel Blob Storage (free tier: 1GB)
    if (process.env.BLOB_READ_WRITE_TOKEN) {
      const { put } = await import('@vercel/blob');
      const blob = await put(`shapes/${uploadId}/${uploadedFile.originalFilename}`, fileData, {
        access: 'public',
      });
      
      // Queue for processing
      await queueShapeFileProcessing({
        uploadId,
        fileName: uploadedFile.originalFilename,
        fileUrl: blob.url,
        fileSize: uploadedFile.size,
        uploadedAt: new Date().toISOString(),
        processingOptions: fields
      });
    } 
    // Option 2: Forward to local storage via API
    else {
      const formData = new FormData();
      formData.append('file', new Blob([fileData]), uploadedFile.originalFilename);
      Object.keys(fields).forEach(key => {
        formData.append(key, fields[key]);
      });

      const response = await fetch(`${process.env.INTERNAL_API_URL}/api/v1/internal/shapes/upload`, {
        method: 'POST',
        headers: {
          'X-Internal-Key': process.env.INTERNAL_API_KEY!,
          'X-Upload-Id': uploadId
        },
        body: formData
      });

      if (!response.ok) {
        throw new Error('Failed to forward file to storage');
      }
    }

    // Clean up temp file
    await fs.unlink(uploadedFile.filepath);

    // Return success response
    return res.status(200).json({
      message: 'File uploaded successfully',
      uploadId,
      fileName: uploadedFile.originalFilename,
      fileSize: uploadedFile.size,
      processingStatus: 'queued'
    });

  } catch (error) {
    console.error('Upload error:', error);
    return res.status(500).json({ 
      error: 'Failed to process upload' 
    });
  }
}

async function queueShapeFileProcessing(data: any) {
  // Similar queue options as telemetry
  // For production, trigger a webhook or use a queue service
  
  // Option 1: Direct webhook to processing service
  await fetch(`${process.env.INTERNAL_API_URL}/api/v1/internal/shapes/process`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Internal-Key': process.env.INTERNAL_API_KEY!
    },
    body: JSON.stringify(data)
  });
}