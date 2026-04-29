"use client";

import { Autocomplete } from "@react-google-maps/api";
import { TextInput, Button } from "@mantine/core";
import { useState, useRef } from "react";

// NSW bounding box — strongly bias results to NSW
const NSW_BOUNDS = {
  north: -28.15,
  south: -37.51,
  east: 153.64,
  west: 140.99,
};

interface Props {
  onPlaceSelected: (lat: number, lng: number, address: string) => void;
  loading?: boolean;
}

export default function AddressSearch({ onPlaceSelected, loading }: Props) {
  const [value, setValue] = useState("");
  const autocompleteRef = useRef<google.maps.places.Autocomplete | null>(null);

  const onLoad = (autocomplete: google.maps.places.Autocomplete) => {
    autocompleteRef.current = autocomplete;
    // Set bounds to NSW and restrict to them
    autocomplete.setBounds(NSW_BOUNDS);
    autocomplete.setOptions({ strictBounds: true });
  };

  const onPlaceChanged = () => {
    const place = autocompleteRef.current?.getPlace();
    if (place?.geometry?.location) {
      const lat = place.geometry.location.lat();
      const lng = place.geometry.location.lng();
      const address = place.formatted_address || value;
      setValue(address);
      onPlaceSelected(lat, lng, address);
    }
  };

  return (
    <div className="address-search-row">
      <Autocomplete
        onLoad={onLoad}
        onPlaceChanged={onPlaceChanged}
        options={{
          componentRestrictions: { country: "au" },
          types: ["address"],
        }}
      >
        <TextInput
          label="Your address"
          placeholder="e.g. 42 Wallaby Way, Sydney NSW"
          value={value}
          onChange={(e) => setValue(e.currentTarget.value)}
        />
      </Autocomplete>
      <Button
        loading={loading}
        disabled={!value}
        onClick={onPlaceChanged}
        style={{ alignSelf: "flex-end" }}
      >
        Search
      </Button>
    </div>
  );
}
