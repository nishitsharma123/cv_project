import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { FileUpload } from '../components/FileUpload';

describe('FileUpload component', () => {
  it('renders upload prompt when no file is selected', () => {
    render(<FileUpload selectedFile={null} onFileSelected={vi.fn()} />);
    expect(screen.getByText(/Drag and drop your handwritten form here/i)).toBeInTheDocument();
    expect(screen.getByText(/Accepted formats:/i)).toBeInTheDocument();
  });

  it('rejects oversized files exceeding 15MB', () => {
    const handleFileSelected = vi.fn();
    render(<FileUpload selectedFile={null} onFileSelected={handleFileSelected} />);

    // Create 16MB dummy file
    const oversizedFile = new File(['x'.repeat(100)], 'large_form.png', { type: 'image/png' });
    Object.defineProperty(oversizedFile, 'size', { value: 16 * 1024 * 1024 });

    const input = screen.getByLabelText(/Upload document image/i);
    fireEvent.drop(input, {
      dataTransfer: { files: [oversizedFile] },
    });

    expect(handleFileSelected).not.toHaveBeenCalled();
    expect(screen.getByText(/exceeds maximum limit of 15MB/i)).toBeInTheDocument();
  });

  it('rejects empty files (0 bytes)', () => {
    const handleFileSelected = vi.fn();
    render(<FileUpload selectedFile={null} onFileSelected={handleFileSelected} />);

    const emptyFile = new File([], 'empty.png', { type: 'image/png' });
    Object.defineProperty(emptyFile, 'size', { value: 0 });

    const input = screen.getByLabelText(/Upload document image/i);
    fireEvent.drop(input, {
      dataTransfer: { files: [emptyFile] },
    });

    expect(handleFileSelected).not.toHaveBeenCalled();
    expect(screen.getByText(/file is empty \(0 bytes\)/i)).toBeInTheDocument();
  });

  it('rejects unsupported file formats', () => {
    const handleFileSelected = vi.fn();
    render(<FileUpload selectedFile={null} onFileSelected={handleFileSelected} />);

    const textFile = new File(['some text'], 'document.txt', { type: 'text/plain' });

    const input = screen.getByLabelText(/Upload document image/i);
    fireEvent.drop(input, {
      dataTransfer: { files: [textFile] },
    });

    expect(handleFileSelected).not.toHaveBeenCalled();
    expect(screen.getByText(/Unsupported format\. Please upload a JPEG or PNG/i)).toBeInTheDocument();
  });

  it('accepts valid PNG image and invokes callback', () => {
    const handleFileSelected = vi.fn();
    render(<FileUpload selectedFile={null} onFileSelected={handleFileSelected} />);

    const validFile = new File(['valid png data'], 'test_form.png', { type: 'image/png' });

    const input = screen.getByLabelText(/Upload document image/i);
    fireEvent.drop(input, {
      dataTransfer: { files: [validFile] },
    });

    expect(handleFileSelected).toHaveBeenCalledWith(validFile);
  });

  it('renders selected file information and allows removal', () => {
    const handleFileSelected = vi.fn();
    const validFile = new File(['dummy'], 'sample_invoice.jpg', { type: 'image/jpeg' });
    render(<FileUpload selectedFile={validFile} onFileSelected={handleFileSelected} />);

    expect(screen.getByText('sample_invoice.jpg')).toBeInTheDocument();
    const removeBtn = screen.getByLabelText(/Remove selected file/i);
    fireEvent.click(removeBtn);

    expect(handleFileSelected).toHaveBeenCalledWith(null);
  });
});
