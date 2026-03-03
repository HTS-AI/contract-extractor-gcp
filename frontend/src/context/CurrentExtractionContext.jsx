import React, { createContext, useContext, useState, useCallback } from 'react'

const CurrentExtractionContext = createContext(null)

export function CurrentExtractionProvider({ children }) {
  const [currentExtractionId, setCurrentExtractionId] = useState(null)
  const value = { currentExtractionId, setCurrentExtractionId }
  return (
    <CurrentExtractionContext.Provider value={value}>
      {children}
    </CurrentExtractionContext.Provider>
  )
}

export function useCurrentExtraction() {
  const ctx = useContext(CurrentExtractionContext)
  return ctx || { currentExtractionId: null, setCurrentExtractionId: () => {} }
}
