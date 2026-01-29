/**
 * Unusual Options Activity Table
 * AG Grid table for unusual options activity
 * QUANT_INDUSTRY_V1
 */

import React, { useMemo, useCallback } from 'react';
import { AgGridReact } from 'ag-grid-react';
import { ColDef, ICellRendererParams, ValueFormatterParams } from 'ag-grid-community';
import { UnusualActivity } from '@/types/options-flow';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';

interface UnusualActivityTableProps {
  data: UnusualActivity[];
  onRowClick?: (activity: UnusualActivity) => void;
}

const SentimentBadge: React.FC<{ value: string }> = ({ value }) => {
  const colors = {
    bullish: 'bg-green-500/20 text-green-400 border-green-500/30',
    bearish: 'bg-red-500/20 text-red-400 border-red-500/30',
    neutral: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium border ${colors[value as keyof typeof colors] || colors.neutral}`}>
      {value?.toUpperCase()}
    </span>
  );
};

const FlowTypeBadge: React.FC<{ value: string }> = ({ value }) => {
  const colors = {
    sweep: 'bg-purple-500/20 text-purple-400',
    block: 'bg-blue-500/20 text-blue-400',
    split: 'bg-yellow-500/20 text-yellow-400',
    regular: 'bg-gray-500/20 text-gray-400',
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[value as keyof typeof colors] || colors.regular}`}>
      {value?.toUpperCase()}
    </span>
  );
};

export const UnusualActivityTable: React.FC<UnusualActivityTableProps> = ({ data, onRowClick }) => {
  const columnDefs = useMemo<ColDef<UnusualActivity>[]>(() => [
    {
      field: 'timestamp',
      headerName: 'Time',
      width: 100,
      valueFormatter: (p: ValueFormatterParams) => 
        p.value ? new Date(p.value).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }) : '',
    },
    {
      field: 'symbol',
      headerName: 'Symbol',
      width: 90,
      cellClass: 'font-bold text-white',
    },
    {
      field: 'optionType',
      headerName: 'C/P',
      width: 60,
      cellRenderer: (p: ICellRendererParams) => (
        <span className={p.value === 'call' ? 'text-green-400' : 'text-red-400'}>
          {p.value === 'call' ? 'C' : 'P'}
        </span>
      ),
    },
    {
      field: 'strike',
      headerName: 'Strike',
      width: 80,
      valueFormatter: (p: ValueFormatterParams) => `$${p.value?.toFixed(0)}`,
    },
    {
      field: 'expiration',
      headerName: 'Exp',
      width: 90,
      valueFormatter: (p: ValueFormatterParams) => 
        p.value ? new Date(p.value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '',
    },
    {
      field: 'premium',
      headerName: 'Premium',
      width: 100,
      valueFormatter: (p: ValueFormatterParams) => 
        p.value >= 1000000 ? `$${(p.value / 1000000).toFixed(1)}M` : `$${(p.value / 1000).toFixed(0)}K`,
      cellClass: 'text-right font-medium',
    },
    {
      field: 'volume',
      headerName: 'Vol',
      width: 80,
      valueFormatter: (p: ValueFormatterParams) => p.value?.toLocaleString(),
      cellClass: 'text-right',
    },
    {
      field: 'openInterest',
      headerName: 'OI',
      width: 80,
      valueFormatter: (p: ValueFormatterParams) => p.value?.toLocaleString(),
      cellClass: 'text-right',
    },
    {
      field: 'volumeOIRatio',
      headerName: 'Vol/OI',
      width: 80,
      valueFormatter: (p: ValueFormatterParams) => `${p.value?.toFixed(1)}x`,
      cellClass: 'text-right',
      cellClassRules: {
        'text-yellow-400': (p) => p.value >= 2 && p.value < 5,
        'text-orange-400': (p) => p.value >= 5,
      },
    },
    {
      field: 'impliedVolatility',
      headerName: 'IV',
      width: 70,
      valueFormatter: (p: ValueFormatterParams) => `${(p.value * 100).toFixed(0)}%`,
      cellClass: 'text-right',
    },
    {
      field: 'flowType',
      headerName: 'Type',
      width: 80,
      cellRenderer: (p: ICellRendererParams) => <FlowTypeBadge value={p.value} />,
    },
    {
      field: 'aggressor',
      headerName: 'Side',
      width: 60,
      cellRenderer: (p: ICellRendererParams) => (
        <span className={p.value === 'buy' ? 'text-green-400' : p.value === 'sell' ? 'text-red-400' : 'text-gray-400'}>
          {p.value?.toUpperCase()}
        </span>
      ),
    },
    {
      field: 'sentiment',
      headerName: 'Sent',
      width: 90,
      cellRenderer: (p: ICellRendererParams) => <SentimentBadge value={p.value} />,
    },
    {
      field: 'unusualScore',
      headerName: 'Score',
      width: 70,
      valueFormatter: (p: ValueFormatterParams) => p.value?.toFixed(1),
      cellClassRules: {
        'text-yellow-400': (p) => p.value >= 7 && p.value < 8.5,
        'text-orange-400': (p) => p.value >= 8.5,
      },
    },
  ], []);

  const defaultColDef = useMemo(() => ({
    sortable: true,
    filter: true,
    resizable: true,
  }), []);

  const onRowClicked = useCallback((event: any) => {
    if (onRowClick) {
      onRowClick(event.data);
    }
  }, [onRowClick]);

  return (
    <div className="h-full w-full ag-theme-alpine-dark">
      <AgGridReact<UnusualActivity>
        rowData={data}
        columnDefs={columnDefs}
        defaultColDef={defaultColDef}
        onRowClicked={onRowClicked}
        rowSelection="single"
        animateRows={true}
        suppressCellFocus={true}
        getRowId={(params) => params.data.id}
        rowClass="cursor-pointer hover:bg-gray-700/50"
      />
    </div>
  );
};

export default UnusualActivityTable;
