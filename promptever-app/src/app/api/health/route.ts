import { NextResponse } from 'next/server';

const RAG_API_URL = process.env.RAG_API_URL || 'http://rag-api:8000';

export async function GET() {
  try {
    const response = await fetch(`${RAG_API_URL}/health`);
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { status: 'error', error: String(error) },
      { status: 500 }
    );
  }
}